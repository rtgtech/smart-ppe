"""Fail-safe, edge-owned gate entry workflow."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import statistics
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

import cv2
import httpx
import numpy as np
from fastapi import APIRouter, Depends, Header, HTTPException, WebSocket, WebSocketDisconnect
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal, get_db
from app.core.audit import create_audit_log
from app.models import Alert, AttendanceLog, ComplianceLog, Device, Gate, GateEvent, PpeDetection, PpeItem, SyncOutbox, Worker
from app.services.ppe_compliance import PPE_ITEM_SPECS, PersonTracker
from app.services.vision import MAX_FRAME_BYTES, decode_jpeg, infer_frame, vision_lock

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/entry", tags=["entry"])
settings = get_settings()
REQUIRED = {spec["display_name"]: label for label, spec in PPE_ITEM_SPECS.items()}
TRACK_ANCHOR = "Helmet"
WINDOW = 5
CONFIRM = 3
_event_locks: dict[str, asyncio.Lock] = {}
_sync_task: asyncio.Task | None = None
_maintenance_task: asyncio.Task | None = None
_central_online = False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def _load(raw: str, default: Any) -> Any:
    try:
        return json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return default


def _dump(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)


def _device(db: Session) -> Device:
    device = db.query(Device).filter(Device.serial_number == settings.edge_device_serial).one_or_none()
    if device is None or device.status != "ONLINE" or device.device_type != "AI_CAMERA":
        raise HTTPException(503, "The configured edge AI camera is not online")
    if device.gate is None or device.gate.status != "ACTIVE":
        raise HTTPException(503, "The configured gate is not active")
    if device.gate.latitude is None or device.gate.longitude is None:
        raise HTTPException(503, "The configured gate coordinates are required")
    return device


def _require_ppe_catalog(db: Session) -> None:
    configured = {
        item.name
        for item in db.query(PpeItem).filter(PpeItem.is_mandatory.is_(True)).all()
    }
    if configured != set(REQUIRED):
        raise HTTPException(503, f"{', '.join(REQUIRED)} must be configured as mandatory PPE")


def _event_dict(event: GateEvent) -> dict[str, Any]:
    evidence = _load(event.evidence_json, {})
    worker = None
    if event.worker:
        worker = {
            "worker_id": event.worker.worker_id,
            "employee_code": event.worker.employee_code,
            "name": event.worker.name,
            "department": event.worker.department.name if event.worker.department else "",
        }
    return {
        "event_id": event.event_id,
        "lifecycle": event.lifecycle,
        "phase": event.phase,
        "verdict": event.verdict,
        "worker": worker,
        "gate": {
            "gate_id": event.gate_id, "name": event.gate.name, "location": event.gate.location,
            "latitude": event.gate_latitude, "longitude": event.gate_longitude,
        },
        "device": {"device_id": event.device_id, "serial_number": event.device.serial_number},
        "edge_timestamp": _aware(event.edge_timestamp).isoformat(),
        "finalized_at": _aware(event.finalized_at).isoformat() if event.finalized_at else None,
        "deadlines": {"identity": evidence.get("identity_deadline"), "evidence": evidence.get("evidence_deadline")},
        "evidence": evidence.get("summary", {}),
        "reasons": _load(event.reasons_json, []),
        "qr_results": _load(event.qr_results_json, []),
        "interventions": _load(event.interventions_json, {"barrier": "LOCKED", "indicator": "AMBER", "audible_warning": False}),
        "identity_confidence": event.identity_confidence,
        "ppe_confidence": event.ppe_confidence,
        "evidence_confidence": event.evidence_confidence,
        "evidence_source": event.evidence_source.split(","),
        "offline": event.offline_flag,
        "sync_status": event.sync_status,
    }


def _decode_qr(image: np.ndarray) -> list[str]:
    detector = cv2.QRCodeDetector()
    values: list[str] = []
    try:
        ok, decoded, _, _ = detector.detectAndDecodeMulti(image)
        if ok:
            values.extend(value.strip() for value in decoded if value and value.strip())
    except (cv2.error, ValueError):
        pass
    if not values:
        try:
            value, _, _ = detector.detectAndDecode(image)
            if value and value.strip():
                values.append(value.strip())
        except cv2.error:
            pass
    return list(dict.fromkeys(values))


def _frame_evidence(encoded: bytes, persons: list[dict[str, Any]], faces: list[dict[str, Any]]) -> dict[str, Any]:
    image = decode_jpeg(encoded)
    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    luminance = float(np.mean(gray))
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    quality = settings.entry_min_luminance <= luminance <= settings.entry_max_luminance and sharpness >= settings.entry_min_laplacian_variance

    multiple = len(faces) > 1 or len(persons) > 1
    person = persons[0] if len(persons) == 1 else None
    person_box = person["bbox"] if person else None
    face = faces[0] if len(faces) == 1 else None
    framing = False
    if person_box and face:
        px1, py1, px2, py2 = person_box
        fx1, fy1, fx2, fy2 = face["bbox"]
        face_center = ((fx1 + fx2) / 2, (fy1 + fy2) / 2)
        margin_x, margin_y = width * settings.entry_frame_margin_ratio, height * settings.entry_frame_margin_ratio
        framing = (
            (py2 - py1) / height >= settings.entry_person_min_height_ratio
            and px1 >= margin_x and py1 >= margin_y and px2 <= width - margin_x and py2 <= height - margin_y
            and px1 <= face_center[0] <= px2 and py1 <= face_center[1] <= py2
        )

    if multiple:
        identity = {"state": "MULTIPLE", "person_id": None, "confidence": 0}
    elif face and face.get("recognized"):
        identity = {"state": "MATCH", "person_id": face.get("person_id"), "confidence": float(face.get("similarity") or 0)}
    elif face:
        identity = {"state": "UNKNOWN", "person_id": None, "confidence": float(face.get("similarity") or 0)}
    else:
        identity = {"state": "NONE", "person_id": None, "confidence": 0}

    visual: dict[str, dict[str, Any]] = {}
    for item_name, label in REQUIRED.items():
        worn_state = person[label] if person else "UNKNOWN"
        associations = person["associations"][label] if person else []
        region_names = PPE_ITEM_SPECS[label]["regions"]
        region_boxes = [person["rois"][name]["bbox"] for name in region_names] if person else []
        if framing and quality and worn_state == "YES":
            visual[item_name] = {
                "state": "POSITIVE",
                "confidence": person[f"{label}_confidence"],
                "bbox": [row["bbox"] for row in associations],
                "track_id": person["track_id"],
                "roi": region_boxes,
                "association_score": min(row["association_score"] for row in associations),
                "worn_state": worn_state,
            }
        elif framing and quality and worn_state == "NO":
            negative_associations = [row for row in associations if row.get("is_negative")]
            visual[item_name] = {
                "state": "NEGATIVE",
                "confidence": person[f"{label}_confidence"],
                "bbox": [row["bbox"] for row in negative_associations] or None,
                "track_id": person["track_id"],
                "roi": region_boxes,
                "association_score": min(
                    (row["association_score"] for row in negative_associations),
                    default=None,
                ),
                "worn_state": worn_state,
            }
        else:
            visual[item_name] = {
                "state": "UNKNOWN", "confidence": None, "bbox": None,
                "track_id": person["track_id"] if person else None,
                "roi": region_boxes, "association_score": None, "worn_state": "UNKNOWN",
            }

    return {
        "at": _now().isoformat(), "identity": identity, "multiple": multiple,
        "quality_valid": quality, "framing_valid": framing, "luminance": round(luminance, 1),
        "sharpness": round(sharpness, 1), "visual": visual, "qr_codes": _decode_qr(image),
    }


def _summarize(db: Session, event: GateEvent, state: dict[str, Any]) -> tuple[dict[str, Any], Worker | None]:
    frames = state.get("frames", [])[-WINDOW:]
    track_counts: Counter[int] = Counter()
    for frame in frames:
        track_id = frame.get("visual", {}).get(TRACK_ANCHOR, {}).get("track_id")
        if track_id is not None and not frame.get("multiple"):
            track_counts[track_id] += 1
    candidate_track = track_counts.most_common(1)[0][0] if track_counts else None
    tracked_frames = [
        frame for frame in frames
        if candidate_track is None or frame.get("visual", {}).get(TRACK_ANCHOR, {}).get("track_id") == candidate_track
    ]
    matches: dict[str, list[float]] = {}
    for frame in tracked_frames:
        identity = frame["identity"]
        if identity["state"] == "MATCH" and identity.get("person_id"):
            matches.setdefault(identity["person_id"], []).append(identity["confidence"])
    candidate = max(matches, key=lambda key: len(matches[key]), default=None)
    worker = None
    if candidate and len(matches[candidate]) >= CONFIRM and not any(frame["multiple"] for frame in tracked_frames):
        worker = db.query(Worker).filter(Worker.employee_code.ilike(candidate), Worker.status == "ACTIVE").one_or_none()

    framing_count = sum(frame["framing_valid"] and frame["quality_valid"] for frame in tracked_frames)
    visual: dict[str, Any] = {}
    visual_confidences: list[float] = []
    for item in REQUIRED:
        positives = [frame["visual"][item] for frame in tracked_frames if frame["visual"][item]["state"] == "POSITIVE"]
        negatives = sum(frame["visual"][item]["state"] == "NEGATIVE" for frame in tracked_frames)
        status = "CONFIRMED" if len(positives) >= CONFIRM else "MISSING" if negatives >= CONFIRM else "UNSTABLE"
        confidence = statistics.median([row["confidence"] for row in positives]) if positives else None
        representative = max(positives, key=lambda row: row["confidence"]) if positives else next(
            (frame["visual"][item] for frame in reversed(tracked_frames) if frame["visual"][item]["state"] == "NEGATIVE"),
            {},
        )
        if status == "CONFIRMED" and confidence is not None:
            visual_confidences.append(confidence)
        visual[item] = {
            "state": status,
            "positive_frames": len(positives),
            "negative_frames": negatives,
            "confidence": confidence,
            "bbox": representative.get("bbox"),
            "track_id": representative.get("track_id"),
            "roi": representative.get("roi"),
            "association_score": representative.get("association_score"),
            "worn_state": "YES" if status == "CONFIRMED" else "NO" if status == "MISSING" else "UNKNOWN",
        }

    identity_confidence = statistics.median(matches.get(candidate, [])) * 100 if worker else None
    summary = {
        "identity": {"state": "CONFIRMED" if worker else "UNSTABLE", "supporting_frames": len(matches.get(candidate, [])), "confidence": identity_confidence},
        "framing": {"state": "CONFIRMED" if framing_count >= CONFIRM else "UNSTABLE", "supporting_frames": framing_count},
        "visual": visual, "frames_in_window": len(frames), "track_id": candidate_track,
    }
    state["summary"] = summary
    event.identity_confidence = round(identity_confidence, 1) if identity_confidence is not None else None
    visual_support = [max(visual[item]["positive_frames"], visual[item]["negative_frames"]) / WINDOW for item in REQUIRED]
    event.ppe_confidence = round((min(visual_confidences) if len(visual_confidences) == len(REQUIRED) else min(visual_support)) * 100, 1)
    ratios = [len(matches.get(candidate, [])) / WINDOW if candidate else 0, framing_count / WINDOW]
    ratios.extend(max(visual[item]["positive_frames"], visual[item]["negative_frames"]) / WINDOW for item in REQUIRED)
    event.evidence_confidence = round(min(ratios) * 100, 1)
    return summary, worker


def _finalize(
    db: Session,
    event: GateEvent,
    verdict: str,
    worker: Worker | None,
    reasons: list[str],
    summary: dict[str, Any],
    state: dict[str, Any],
) -> None:
    """
    Finalize a gate event and persist:

        1. GateEvent
        2. ComplianceLog
        3. PPE detections
        4. AttendanceLog when entry is allowed
        5. Alert when required
        6. SyncOutbox when central sync is enabled

    This function is intentionally transactional.
    The caller commits the SQLAlchemy session.
    """

    if event.lifecycle == "FINALIZED":
        logger.info(
            "Finalize skipped | event_id=%s already finalized",
            event.event_id,
        )
        return

    now = _now()

    logger.info(
        "Finalizing gate event | event_id=%s verdict=%s worker_id=%s",
        event.event_id,
        verdict,
        worker.worker_id if worker else None,
    )

    # ---------------------------------------------------------
    # 1. Finalize GateEvent
    # ---------------------------------------------------------

    event.lifecycle = "FINALIZED"
    event.phase = "FINAL"
    event.verdict = verdict
    event.finalized_at = now
    event.worker_id = worker.worker_id if worker else None

    event.reasons_json = _dump(reasons)
    event.qr_results_json = _dump([])

    event.interventions_json = _dump(
        {
            "barrier": "UNLOCKED" if verdict == "ALLOWED" else "LOCKED",
            "indicator": (
                "GREEN"
                if verdict == "ALLOWED"
                else "RED"
                if verdict == "DENIED"
                else "AMBER"
            ),
            "audible_warning": verdict == "DENIED",
        }
    )

    event.offline_flag = (
        bool(settings.central_sync_url)
        and not _central_online
    )

    event.sync_status = (
        "PENDING"
        if settings.central_sync_url
        else "SYNCED"
    )

    event.evidence_json = _dump(state)

    # ---------------------------------------------------------
    # 2. Load PPE catalog
    # ---------------------------------------------------------

    log: ComplianceLog | None = None

    items = (
        db.query(PpeItem)
        .filter(PpeItem.name.in_(REQUIRED))
        .all()
    )

    item_by_name = {
        item.name: item
        for item in items
    }

    logger.info(
        "PPE catalog loaded | event_id=%s items=%s",
        event.event_id,
        list(item_by_name.keys()),
    )

    # ---------------------------------------------------------
    # 3. Create compliance log
    # ---------------------------------------------------------

    if worker:
        visual_passes = sum(
            summary["visual"][name]["state"] == "CONFIRMED"
            for name in REQUIRED
        )

        compliance_score = round(
            visual_passes * 100 / len(REQUIRED),
            1,
        )

        overall_status = (
            "COMPLIANT"
            if verdict == "ALLOWED"
            else "DENIED"
            if verdict == "DENIED"
            else "NON_COMPLIANT"
        )

        log = ComplianceLog(
            event_id=event.event_id,
            final_verdict=verdict,
            worker_id=worker.worker_id,
            gate_id=event.gate_id,
            entry_time=event.edge_timestamp,
            overall_status=overall_status,
            compliance_score=compliance_score,
            confidence_score=event.evidence_confidence,
            latitude=event.gate_latitude,
            longitude=event.gate_longitude,
            offline_flag=event.offline_flag,
            sync_status=event.sync_status,
        )

        db.add(log)

        # Flush is required so SQLAlchemy generates log.log_id
        # before PPE detections reference it.
        db.flush()

        logger.info(
            "Compliance saved | "
            "event_id=%s log_id=%s worker_id=%s gate_id=%s "
            "status=%s score=%.1f confidence=%s",
            event.event_id,
            log.log_id,
            worker.worker_id,
            event.gate_id,
            overall_status,
            compliance_score,
            event.evidence_confidence,
        )

        # -----------------------------------------------------
        # 4. Create PPE detections
        # -----------------------------------------------------

        detection_count = 0

        for name in REQUIRED:
            item = item_by_name.get(name)

            if not item:
                logger.warning(
                    "PPE catalog item missing | "
                    "event_id=%s ppe_name=%s",
                    event.event_id,
                    name,
                )
                continue

            visual = summary["visual"][name]

            detected = (
                visual["state"] == "CONFIRMED"
            )

            confidence_score = (
                (visual["confidence"] or 0) * 100
                if visual["confidence"] is not None
                else None
            )

            detection = PpeDetection(
                log_id=log.log_id,
                ppe_id=item.ppe_id,
                detected=detected,
                confidence_score=confidence_score,
                bounding_box=_dump({
                    "detection": visual.get("bbox"),
                    "roi": visual.get("roi"),
                    "track_id": visual.get("track_id"),
                    "association_score": visual.get("association_score"),
                }),
                detection_source="AI",
                evidence_state=visual["state"],
                assignment_result=visual.get("worn_state"),
            )

            db.add(detection)
            detection_count += 1

            logger.info(
                "PPE detection saved | "
                "event_id=%s log_id=%s ppe_id=%s ppe=%s "
                "detected=%s confidence=%s state=%s source=AI",
                event.event_id,
                log.log_id,
                item.ppe_id,
                name,
                detected,
                confidence_score,
                visual["state"],
            )

        logger.info(
            "PPE detections prepared | "
            "event_id=%s log_id=%s count=%s",
            event.event_id,
            log.log_id,
            detection_count,
        )

        # -----------------------------------------------------
        # 5. Attendance
        # -----------------------------------------------------

        if verdict == "ALLOWED":
            attendance = AttendanceLog(
                event_id=event.event_id,
                worker_id=worker.worker_id,
                gate_id=event.gate_id,
                entry_time=event.edge_timestamp,
                status="INSIDE",
            )

            db.add(attendance)

            logger.info(
                "Attendance prepared | "
                "event_id=%s worker_id=%s gate_id=%s status=INSIDE",
                event.event_id,
                worker.worker_id,
                event.gate_id,
            )

        else:
            logger.info(
                "Attendance not created | "
                "event_id=%s worker_id=%s verdict=%s",
                event.event_id,
                worker.worker_id,
                verdict,
            )

    else:
        logger.warning(
            "Compliance/attendance not created because worker "
            "identity was not confirmed | event_id=%s verdict=%s reasons=%s",
            event.event_id,
            verdict,
            reasons,
        )

    # ---------------------------------------------------------
    # 6. Alerts
    # ---------------------------------------------------------

    identity_alert = (
        verdict == "HOLD"
        and any(
            reason in reasons
            for reason in (
                "UNKNOWN_FACE",
                "MULTIPLE_IDENTITIES",
                "MULTIPLE_PERSONS",
            )
        )
    )

    if verdict == "DENIED" or identity_alert:
        alert = Alert(
            event_id=event.event_id,
            gate_id=event.gate_id,
            log_id=log.log_id if log else None,
            worker_id=worker.worker_id if worker else None,
            alert_type=(
                "GATE_COMPLIANCE_DENIED"
                if verdict == "DENIED"
                else "GATE_IDENTITY_HOLD"
            ),
            severity=(
                "CRITICAL"
                if verdict == "DENIED"
                else "WARNING"
            ),
            message="; ".join(reasons),
            status="ACTIVE",
        )

        db.add(alert)

        logger.warning(
            "Alert created | "
            "event_id=%s worker_id=%s type=%s severity=%s reasons=%s",
            event.event_id,
            worker.worker_id if worker else None,
            alert.alert_type,
            alert.severity,
            reasons,
        )

    # ---------------------------------------------------------
    # 7. Prepare central sync payload
    # ---------------------------------------------------------

    payload = _event_dict(event)

    payload_json = _dump(
        {
            "schema_version": 1,
            "event": payload,
        }
    )

    payload_hash = hashlib.sha256(
        payload_json.encode()
    ).hexdigest()

    event.payload_hash = payload_hash

    if settings.central_sync_url:
        db.add(
            SyncOutbox(
                event_id=event.event_id,
                payload_json=payload_json,
                payload_hash=payload_hash,
                next_retry_at=now,
            )
        )

        logger.info(
            "Sync outbox record created | "
            "event_id=%s sync_status=%s",
            event.event_id,
            event.sync_status,
        )

    # ---------------------------------------------------------
    # 8. Audit log — gate event finalized
    # ---------------------------------------------------------

    create_audit_log(
        db,
        category="GATE_EVENT",
        action="GATE_FINALIZED",
        status=verdict,
        message=f"Gate event finalized | verdict={verdict} reasons={reasons}",
        event_id=event.event_id,
        worker_id=worker.worker_id if worker else None,
        gate_id=event.gate_id,
        metadata={
            "verdict": verdict,
            "reasons": reasons,
            "identity_confidence": event.identity_confidence,
            "ppe_confidence": event.ppe_confidence,
            "evidence_confidence": event.evidence_confidence,
            "offline": event.offline_flag,
        },
    )

    if worker:
        # Compliance audit
        compliance_overall = (
            "COMPLIANT"
            if verdict == "ALLOWED"
            else "DENIED"
            if verdict == "DENIED"
            else "NON_COMPLIANT"
        )
        create_audit_log(
            db,
            category="COMPLIANCE",
            action="COMPLIANCE_CREATED",
            status=compliance_overall,
            message=(
                f"Compliance record created | "
                f"verdict={verdict} status={compliance_overall}"
            ),
            event_id=event.event_id,
            worker_id=worker.worker_id,
            gate_id=event.gate_id,
            metadata={
                "final_verdict": verdict,
                "overall_status": compliance_overall,
                "compliance_score": (
                    log.compliance_score if log else None
                ),
                "confidence_score": event.evidence_confidence,
            },
        )

        # PPE detection audits
        for name in REQUIRED:
            visual = summary["visual"][name]
            create_audit_log(
                db,
                category="PPE",
                action="PPE_DETECTION",
                status=visual["state"],
                message=(
                    f"PPE detection | "
                    f"ppe={name} state={visual['state']} "
                    f"detected={visual['state'] == 'CONFIRMED'}"
                ),
                event_id=event.event_id,
                worker_id=worker.worker_id,
                gate_id=event.gate_id,
                metadata={
                    "ppe_name": name,
                    "detected": visual["state"] == "CONFIRMED",
                    "evidence_state": visual["state"],
                    "confidence": visual.get("confidence"),
                    "detection_source": "AI",
                },
            )

        if verdict == "ALLOWED":
            create_audit_log(
                db,
                category="ATTENDANCE",
                action="ATTENDANCE_CREATED",
                status="INSIDE",
                message="Attendance created | worker entered gate",
                event_id=event.event_id,
                worker_id=worker.worker_id,
                gate_id=event.gate_id,
                metadata={"entry_status": "INSIDE"},
            )
        else:
            create_audit_log(
                db,
                category="ATTENDANCE",
                action="ATTENDANCE_SKIPPED",
                status=verdict,
                message=(
                    f"Attendance not created | "
                    f"verdict={verdict} worker_id={worker.worker_id}"
                ),
                event_id=event.event_id,
                worker_id=worker.worker_id,
                gate_id=event.gate_id,
                metadata={"verdict": verdict, "reasons": reasons},
            )

    # Alert audit (if an alert was created above)
    if verdict == "DENIED" or identity_alert:
        _alert_type = (
            "GATE_COMPLIANCE_DENIED"
            if verdict == "DENIED"
            else "GATE_IDENTITY_HOLD"
        )
        _severity = "CRITICAL" if verdict == "DENIED" else "WARNING"
        create_audit_log(
            db,
            category="ALERT",
            action="ALERT_CREATED",
            status=_severity,
            message=f"Alert created | type={_alert_type} reasons={reasons}",
            event_id=event.event_id,
            worker_id=worker.worker_id if worker else None,
            gate_id=event.gate_id,
            metadata={
                "alert_type": _alert_type,
                "severity": _severity,
                "reasons": reasons,
            },
        )

    logger.info(
        "Gate event finalization complete | "
        "event_id=%s verdict=%s worker_id=%s",
        event.event_id,
        verdict,
        worker.worker_id if worker else None,
    )



def _evaluate(db: Session, event: GateEvent, force: bool = False) -> bool:
    if event.lifecycle == "FINALIZED":
        return True
    state = _load(event.evidence_json, {"frames": []})
    summary, observed_worker = _summarize(db, event, state)
    now = _now()
    if state.get("subject_started_at") and not state.get("identity_deadline"):
        state["identity_deadline"] = (_aware(datetime.fromisoformat(state["subject_started_at"])) + timedelta(seconds=settings.entry_identity_timeout_seconds)).isoformat()

    # The live workflow is intentionally sequential. Once identity is stable,
    # lock the worker and track, discard pre-identity PPE observations, and let
    # the client advance to /entry/compliance for a fresh evidence window.
    if event.phase == "IDENTITY" and observed_worker and not force:
        event.worker_id = observed_worker.worker_id
        event.phase = "EVIDENCE"
        state["locked_identity"] = summary["identity"]
        state["locked_track_id"] = summary.get("track_id")
        state["evidence_started_at"] = now.isoformat()
        state["evidence_deadline"] = (now + timedelta(seconds=settings.entry_evidence_timeout_seconds)).isoformat()
        state["frames"] = []
        summary = {
            "identity": {**summary["identity"], "continuity_state": "PENDING"},
            "framing": {"state": "UNSTABLE", "supporting_frames": 0},
            "visual": {
                name: {
                    "state": "UNSTABLE", "positive_frames": 0, "negative_frames": 0,
                    "confidence": None, "bbox": None, "track_id": state["locked_track_id"],
                    "roi": None, "association_score": None, "worn_state": "UNKNOWN",
                }
                for name in REQUIRED
            },
            "frames_in_window": 0,
            "track_id": state["locked_track_id"],
        }
        state["summary"] = summary
        event.ppe_confidence = 0
        event.evidence_confidence = 0
        event.evidence_json = _dump(state)
        return False

    locked_worker = db.get(Worker, event.worker_id) if event.phase == "EVIDENCE" and event.worker_id else None
    identity_changed = bool(locked_worker and observed_worker and observed_worker.worker_id != locked_worker.worker_id)
    worker = observed_worker
    if event.phase == "EVIDENCE":
        continuity_confirmed = bool(locked_worker and observed_worker and observed_worker.worker_id == locked_worker.worker_id)
        locked_identity = state.get("locked_identity") or summary["identity"]
        summary["identity"] = {
            **locked_identity,
            "continuity_state": "CONFIRMED" if continuity_confirmed else "CHANGED" if identity_changed else "PENDING",
        }
        event.identity_confidence = locked_identity.get("confidence")
        state["summary"] = summary
        worker = locked_worker if continuity_confirmed else None
    elif observed_worker:
        event.worker_id = observed_worker.worker_id

    reasons: list[str] = []
    framing_ok = summary["framing"]["state"] == "CONFIRMED"
    if identity_changed:
        _finalize(db, event, "HOLD", locked_worker, ["IDENTITY_CHANGED"], summary, state)
        return True
    if worker and framing_ok:
        for name, value in summary["visual"].items():
            if value["state"] == "MISSING":
                reasons.append(f"{REQUIRED[name].upper()}_VISUALLY_MISSING")
        if reasons:
            _finalize(db, event, "DENIED", worker, sorted(set(reasons)), summary, state)
            return True
        if all(summary["visual"][name]["state"] == "CONFIRMED" for name in REQUIRED):
            _finalize(db, event, "ALLOWED", worker, [], summary, state)
            return True

    deadline_key = "evidence_deadline" if event.phase == "EVIDENCE" else "identity_deadline"
    deadline = datetime.fromisoformat(state[deadline_key]) if state.get(deadline_key) else None
    expired = deadline is not None and now >= _aware(deadline)
    if not expired and not force:
        event.evidence_json = _dump(state)
        return False

    if not worker:
        frames = state.get("frames", [])[-WINDOW:]
        if sum(frame["identity"]["state"] == "MULTIPLE" for frame in frames) >= CONFIRM:
            reasons.append("MULTIPLE_IDENTITIES")
        elif sum(frame["identity"]["state"] == "UNKNOWN" for frame in frames) >= CONFIRM:
            reasons.append("UNKNOWN_FACE")
        else:
            reasons.append("UNSTABLE_IDENTITY")
        previously_confirmed = locked_worker or (db.get(Worker, event.worker_id) if event.worker_id else None)
        _finalize(db, event, "HOLD", previously_confirmed, reasons, summary, state)
        return True
    if not framing_ok:
        reasons.append("POOR_FRAMING_OR_IMAGE_QUALITY")
    for name in REQUIRED:
        if summary["visual"][name]["state"] == "UNSTABLE":
            reasons.append(f"{REQUIRED[name].upper()}_VISUAL_UNSTABLE")
        elif summary["visual"][name]["state"] == "MISSING":
            reasons.append(f"{REQUIRED[name].upper()}_VISUALLY_MISSING")
    missing_ppe = any(reason.endswith("_MISSING") for reason in reasons)
    verdict = "DENIED" if (framing_ok and missing_ppe) else "HOLD"
    _finalize(db, event, verdict, worker, reasons, summary, state)
    return True



@router.post("/attempts", status_code=201)
def create_attempt(idempotency_key: str = Header(..., alias="Idempotency-Key"), db: Session = Depends(get_db)):
    if settings.deployment_role == "central":
        raise HTTPException(403, "Entry attempts can only run on an edge deployment")
    try:
        event_id = str(uuid.UUID(idempotency_key))
    except ValueError as exc:
        raise HTTPException(422, "Idempotency-Key must be a UUID") from exc
    existing = db.get(GateEvent, event_id)
    if existing:
        return _event_dict(existing)
    device = _device(db)
    _require_ppe_catalog(db)
    event = GateEvent(
        event_id=event_id, gate_id=device.gate_id, device_id=device.device_id,
        gate_latitude=device.gate.latitude, gate_longitude=device.gate.longitude,
        edge_timestamp=_now(), lifecycle="ACTIVE", phase="IDENTITY",
        evidence_json=_dump({"frames": [], "qr_max_counts": {}, "qr_confirmed": {}, "qr_failures": {}}),
        offline_flag=bool(settings.central_sync_url), sync_status="PENDING" if settings.central_sync_url else "SYNCED",
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return _event_dict(event)


@router.get("/attempts/{event_id}")
def get_attempt(event_id: str, db: Session = Depends(get_db)):
    event = db.get(GateEvent, event_id)
    if event is None:
        raise HTTPException(404, "Entry attempt not found")
    return _event_dict(event)


@router.post("/attempts/{event_id}/finalize")
async def finalize_attempt(event_id: str):
    async with _event_locks.setdefault(event_id, asyncio.Lock()):
        db = SessionLocal()
        try:
            event = db.get(GateEvent, event_id)
            if event is None:
                raise HTTPException(404, "Entry attempt not found")
            _evaluate(db, event, force=True)
            db.commit()
            db.refresh(event)
            return _event_dict(event)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()



@router.websocket("/attempts/{event_id}/stream")
async def entry_stream(websocket: WebSocket, event_id: str) -> None:
    await websocket.accept()

    logger.info(
        "Entry stream connected | event_id=%s",
        event_id,
    )

    tracker = PersonTracker()
    db = SessionLocal()

    try:
        event = db.get(GateEvent, event_id)

        if event is None:
            logger.warning(
                "Entry attempt not found | event_id=%s",
                event_id,
            )

            await websocket.send_json(
                {
                    "type": "error",
                    "message": "Entry attempt not found",
                }
            )
            return

        logger.info(
            "Entry attempt loaded | "
            "event_id=%s gate_id=%s worker_id=%s lifecycle=%s",
            event.event_id,
            event.gate_id,
            event.worker_id,
            event.lifecycle,
        )

        await websocket.send_json(
            {
                "type": "entry_meta",
                "entry": _event_dict(event),
            }
        )

    finally:
        db.close()

    try:
        while True:
            message = await websocket.receive()

            if message.get("type") == "websocket.disconnect":
                logger.info(
                    "Entry stream disconnected | event_id=%s",
                    event_id,
                )
                break

            frame = message.get("bytes")

            if frame is None:
                continue

            if len(frame) > MAX_FRAME_BYTES:
                logger.warning(
                    "Frame rejected because it is too large | "
                    "event_id=%s size=%s max=%s",
                    event_id,
                    len(frame),
                    MAX_FRAME_BYTES,
                )

                await websocket.send_json(
                    {
                        "type": "error",
                        "message": "Frame is too large",
                    }
                )
                continue

            async with _event_locks.setdefault(
                event_id,
                asyncio.Lock(),
            ):
                async with vision_lock:

                    # -------------------------------------------------
                    # AI inference
                    # -------------------------------------------------

                    (
                        output,
                        detections,
                        yolo_ms,
                        faces,
                        face_ms,
                        face_error,
                        live_summary,
                        person_results,
                        pose_ms,
                    ) = await asyncio.to_thread(
                        infer_frame,
                        frame,
                        .5,
                        tracker,
                    )

                    evidence = await asyncio.to_thread(
                        _frame_evidence,
                        frame,
                        person_results,
                        faces,
                    )

                    logger.info(
                        "Inference completed | "
                        "event_id=%s detections=%s faces=%s persons=%s "
                        "yolo_ms=%.1f pose_ms=%.1f face_ms=%.1f identity=%s",
                        event_id,
                        len(detections),
                        len(faces),
                        len(person_results),
                        yolo_ms,
                        pose_ms,
                        face_ms,
                        evidence.get("identity", {}).get("state"),
                    )

                db = SessionLocal()

                try:
                    event = db.get(
                        GateEvent,
                        event_id,
                    )

                    if event is None:
                        logger.warning(
                            "Entry attempt disappeared during stream | "
                            "event_id=%s",
                            event_id,
                        )

                        await websocket.send_json(
                            {
                                "type": "error",
                                "message": "Entry attempt not found",
                            }
                        )
                        return

                    if event.lifecycle == "ACTIVE":

                        state = _load(
                            event.evidence_json,
                            {"frames": []},
                        )

                        state.setdefault(
                            "frames",
                            [],
                        ).append(evidence)

                        state["frames"] = state["frames"][-WINDOW:]

                        # Detect when a subject first appears.
                        subject_detected = (
                            evidence["identity"]["state"] != "NONE"
                            or bool(person_results)
                        )

                        if (
                            not state.get("subject_started_at")
                            and subject_detected
                        ):
                            state["subject_started_at"] = evidence["at"]

                            logger.info(
                                "Subject detected | "
                                "event_id=%s timestamp=%s",
                                event_id,
                                evidence["at"],
                            )

                        event.evidence_json = _dump(state)

                        # -------------------------------------------------
                        # Evaluate attendance + PPE compliance
                        # -------------------------------------------------

                        previous_lifecycle = event.lifecycle
                        previous_verdict = event.verdict

                        _evaluate(
                            db,
                            event,
                        )

                        logger.info(
                            "Event evaluated | "
                            "event_id=%s lifecycle=%s->%s "
                            "verdict=%s->%s worker_id=%s",
                            event_id,
                            previous_lifecycle,
                            event.lifecycle,
                            previous_verdict,
                            event.verdict,
                            event.worker_id,
                        )

                        db.commit()

                        db.refresh(event)

                        # -------------------------------------------------
                        # IMPORTANT:
                        # If _evaluate() finalized the event, attendance
                        # and compliance have now been persisted.
                        # -------------------------------------------------

                        if event.lifecycle == "FINALIZED":
                            logger.info(
                                "Event finalized | "
                                "event_id=%s verdict=%s worker_id=%s",
                                event_id,
                                event.verdict,
                                event.worker_id,
                            )

                    metadata = {
                        "type": "frame_meta",
                        "entry": _event_dict(event),
                        "detections": detections,
                        "persons": person_results,
                        "faces": faces,
                        "inference_ms": round(yolo_ms, 1),
                        "pose_inference_ms": round(pose_ms, 1),
                        "face_inference_ms": round(face_ms, 1),
                    }

                    if face_error:
                        metadata["face_error"] = face_error

                        logger.warning(
                            "Face inference error | "
                            "event_id=%s error=%s",
                            event_id,
                            face_error,
                        )

                except Exception:
                    db.rollback()

                    logger.exception(
                        "Database/event processing failed | "
                        "event_id=%s",
                        event_id,
                    )

                    raise

                finally:
                    db.close()

            await websocket.send_json(metadata)
            await websocket.send_bytes(output)

    except (WebSocketDisconnect, RuntimeError):
        logger.info(
            "Entry stream closed | event_id=%s",
            event_id,
        )
        pass

    except Exception:
        logger.exception(
            "Unexpected entry stream error | event_id=%s",
            event_id,
        )
        raise



@router.get("/sync/status")
def sync_status(db: Session = Depends(get_db)):
    rows = db.query(SyncOutbox).order_by(SyncOutbox.outbox_id).all()
    latest_synced = db.query(GateEvent).filter(GateEvent.sync_status == "SYNCED").order_by(GateEvent.finalized_at.desc()).first()
    events = []
    for row in rows:
        event = db.get(GateEvent, row.event_id)
        events.append({
            "id": row.event_id,
            "worker": event.worker.name if event and event.worker else "Gate event",
            "type": "Gate entry", "status": "FAILED" if row.attempts >= 8 else "PENDING",
            "attempts": row.attempts, "last_error": row.last_error,
        })
    return {
        "network": ("ONLINE" if _central_online else "OFFLINE") if settings.central_sync_url else "NOT_CONFIGURED",
        "pending": len(rows),
        "failed": sum(row.attempts >= 8 for row in rows),
        "last_sync": _aware(latest_synced.finalized_at).isoformat() if latest_synced and latest_synced.finalized_at else None,
        "events": events,
    }


@router.post("/sync/events")
def ingest_synced_event(payload: dict[str, Any], authorization: str | None = Header(default=None), db: Session = Depends(get_db)):
    if settings.deployment_role != "central":
        raise HTTPException(403, "The sync receiver is only available on a central deployment")
    if settings.sync_api_token and authorization != f"Bearer {settings.sync_api_token}":
        raise HTTPException(401, "Invalid synchronization token")
    event_data = payload.get("event") or {}
    event_id = event_data.get("event_id")
    if not event_id:
        raise HTTPException(422, "event.event_id is required")
    canonical = _dump(payload)
    digest = hashlib.sha256(canonical.encode()).hexdigest()
    existing = db.get(GateEvent, event_id)
    if existing:
        if existing.payload_hash and existing.payload_hash != digest:
            # Log conflict before raising so it is recorded in this session
            create_audit_log(
                db,
                category="SYNC",
                action="SYNC_CONFLICT",
                status="CONFLICT",
                message=(
                    f"Sync conflict | event_id={event_id} "
                    "payload hash mismatch"
                ),
                event_id=event_id,
                metadata={"reason": "payload_hash_mismatch"},
            )
            db.commit()
            raise HTTPException(409, "The event ID already exists with a different payload")
        create_audit_log(
            db,
            category="SYNC",
            action="SYNC_DUPLICATE",
            status="DUPLICATE",
            message=f"Sync duplicate ignored | event_id={event_id}",
            event_id=event_id,
        )
        db.commit()
        return {"event_id": event_id, "status": "SYNCED", "duplicate": True}
    worker_data = event_data.get("worker")
    worker = db.get(Worker, worker_data["worker_id"]) if worker_data else None
    gate = db.get(Gate, event_data["gate"]["gate_id"])
    device = db.get(Device, event_data["device"]["device_id"])
    if gate is None or device is None or (worker_data and worker is None):
        create_audit_log(
            db,
            category="SYNC",
            action="SYNC_MASTER_DATA_MISMATCH",
            status="REJECTED",
            message=(
                f"Sync rejected | event_id={event_id} "
                "master data mismatch (gate/device/worker not found)"
            ),
            event_id=event_id,
            metadata={
                "gate_missing": gate is None,
                "device_missing": device is None,
                "worker_missing": worker_data is not None and worker is None,
            },
        )
        db.commit()
        raise HTTPException(409, "Central master data does not match the edge event")
    event = GateEvent(
        event_id=event_id, worker_id=worker.worker_id if worker else None, gate_id=gate.gate_id, device_id=device.device_id,
        lifecycle="FINALIZED", phase="FINAL", verdict=event_data["verdict"], gate_latitude=event_data["gate"]["latitude"],
        gate_longitude=event_data["gate"]["longitude"], edge_timestamp=datetime.fromisoformat(event_data["edge_timestamp"]),
        finalized_at=datetime.fromisoformat(event_data["finalized_at"]), received_at=_now(),
        identity_confidence=event_data.get("identity_confidence"), ppe_confidence=event_data.get("ppe_confidence"),
        evidence_confidence=event_data.get("evidence_confidence"), reasons_json=_dump(event_data.get("reasons", [])),
        evidence_json=_dump({"summary": event_data.get("evidence", {})}), qr_results_json=_dump(event_data.get("qr_results", [])),
        interventions_json=_dump(event_data.get("interventions", {})), offline_flag=event_data.get("offline", False),
        sync_status="SYNCED", payload_hash=digest,
    )
    db.add(event)
    # Replicate read models, but never execute interventions on central.
    log = None
    if worker:
        verdict = event.verdict
        log = ComplianceLog(event_id=event_id, final_verdict=verdict, worker_id=worker.worker_id, gate_id=gate.gate_id, entry_time=event.edge_timestamp, overall_status="COMPLIANT" if verdict == "ALLOWED" else "DENIED" if verdict == "DENIED" else "NON_COMPLIANT", compliance_score=100 if verdict == "ALLOWED" else 0, confidence_score=event.evidence_confidence, latitude=event.gate_latitude, longitude=event.gate_longitude, offline_flag=event.offline_flag, sync_status="SYNCED")
        db.add(log)
        db.flush()
        evidence = event_data.get("evidence", {})
        for item in db.query(PpeItem).filter(PpeItem.name.in_(REQUIRED)).all():
            visual = evidence.get("visual", {}).get(item.name, {})
            qr = evidence.get("qr", {}).get(item.name, {})
            db.add(PpeDetection(
                log_id=log.log_id,
                ppe_id=item.ppe_id,
                detected=visual.get("state") == "CONFIRMED",
                confidence_score=(visual.get("confidence") or 0) * 100 if visual.get("confidence") is not None else None,
                bounding_box=_dump({
                    "detection": visual.get("bbox"),
                    "roi": visual.get("roi"),
                    "track_id": visual.get("track_id"),
                    "association_score": visual.get("association_score"),
                }),
                detection_source="AI",
                evidence_state=visual.get("state"),
                assignment_result=visual.get("worn_state"),
            ))
            db.add(PpeDetection(log_id=log.log_id, ppe_id=item.ppe_id, detected=qr.get("state") == "CONFIRMED", confidence_score=min(100, qr.get("max_frames", 0) * 100 / CONFIRM), detection_source="QR", evidence_state=qr.get("state"), observed_identifier=qr.get("identifier"), assignment_result=qr.get("assignment_result")))
        if verdict == "ALLOWED":
            db.add(AttendanceLog(event_id=event_id, worker_id=worker.worker_id, gate_id=gate.gate_id, entry_time=event.edge_timestamp, status="INSIDE"))
    if event.verdict == "DENIED" or any(reason in event_data.get("reasons", []) for reason in ("UNKNOWN_FACE", "MULTIPLE_IDENTITIES", "MULTIPLE_PERSONS")):
        db.add(Alert(event_id=event_id, gate_id=gate.gate_id, log_id=log.log_id if log else None, worker_id=worker.worker_id if worker else None, alert_type="GATE_COMPLIANCE_DENIED" if event.verdict == "DENIED" else "GATE_IDENTITY_HOLD", severity="CRITICAL" if event.verdict == "DENIED" else "WARNING", message="; ".join(event_data.get("reasons", [])), status="ACTIVE"))
    # ---------------------------------------------------------
    # Audit — sync ingestion
    # ---------------------------------------------------------

    verdict = event_data.get("verdict", "")

    create_audit_log(
        db,
        category="SYNC",
        action="SYNC_RECEIVED",
        status="SYNCED",
        message=f"Sync event ingested | event_id={event_id} verdict={verdict}",
        event_id=event_id,
        worker_id=worker.worker_id if worker else None,
        gate_id=gate.gate_id,
        metadata={
            "verdict": verdict,
            "offline": event_data.get("offline", False),
            "reasons": event_data.get("reasons", []),
        },
    )

    if worker and log:
        sync_status_val = (
            "COMPLIANT"
            if verdict == "ALLOWED"
            else "DENIED"
            if verdict == "DENIED"
            else "NON_COMPLIANT"
        )
        create_audit_log(
            db,
            category="SYNC",
            action="SYNCED_COMPLIANCE",
            status=sync_status_val,
            message=(
                f"Synced compliance record | "
                f"log_id={log.log_id} verdict={verdict}"
            ),
            event_id=event_id,
            worker_id=worker.worker_id,
            gate_id=gate.gate_id,
            metadata={
                "log_id": log.log_id,
                "final_verdict": verdict,
                "overall_status": sync_status_val,
                "confidence_score": event.evidence_confidence,
            },
        )

        evidence = event_data.get("evidence", {})
        for item in db.query(PpeItem).filter(PpeItem.name.in_(REQUIRED)).all():
            ai_visual = evidence.get("visual", {}).get(item.name, {})
            qr_visual = evidence.get("qr", {}).get(item.name, {})
            for src, vis in (("AI", ai_visual), ("QR", qr_visual)):
                create_audit_log(
                    db,
                    category="SYNC",
                    action="SYNCED_PPE_DETECTION",
                    status=vis.get("state", "UNKNOWN"),
                    message=(
                        f"Synced PPE detection | "
                        f"ppe={item.name} source={src} "
                        f"state={vis.get('state', 'UNKNOWN')}"
                    ),
                    event_id=event_id,
                    worker_id=worker.worker_id,
                    gate_id=gate.gate_id,
                    metadata={
                        "ppe_name": item.name,
                        "detection_source": src,
                        "detected": vis.get("state") == "CONFIRMED",
                        "evidence_state": vis.get("state"),
                        "confidence": vis.get("confidence"),
                    },
                )

        if verdict == "ALLOWED":
            create_audit_log(
                db,
                category="SYNC",
                action="SYNCED_ATTENDANCE",
                status="INSIDE",
                message=(
                    f"Synced attendance record | "
                    f"worker_id={worker.worker_id} verdict=ALLOWED"
                ),
                event_id=event_id,
                worker_id=worker.worker_id,
                gate_id=gate.gate_id,
                metadata={"entry_status": "INSIDE"},
            )

    db.commit()
    return {"event_id": event_id, "status": "SYNCED", "duplicate": False}


async def _sync_loop() -> None:
    global _central_online
    while True:
        try:
            db = SessionLocal()
            try:
                row = db.query(SyncOutbox).order_by(SyncOutbox.outbox_id).first()
                if row and (row.next_retry_at is None or _aware(row.next_retry_at) <= _now()):
                    payload = json.loads(row.payload_json)
                    headers = {"Authorization": f"Bearer {settings.sync_api_token}"} if settings.sync_api_token else {}
                    try:
                        async with httpx.AsyncClient(timeout=10) as client:
                            response = await client.post(f"{settings.central_sync_url}/api/v1/entry/sync/events", json=payload, headers=headers)
                        response.raise_for_status()
                        _central_online = True
                        event = db.get(GateEvent, row.event_id)
                        if event:
                            event.sync_status = "SYNCED"
                            db.query(ComplianceLog).filter(ComplianceLog.event_id == row.event_id).update({ComplianceLog.sync_status: "SYNCED"})
                        db.delete(row)
                    except Exception as exc:
                        _central_online = False
                        row.attempts += 1
                        row.last_error = str(exc)[:1000]
                        row.next_retry_at = _now() + timedelta(seconds=min(300, 2 ** min(row.attempts, 8)))
                        event = db.get(GateEvent, row.event_id)
                        if event and row.attempts >= 8:
                            event.sync_status = "FAILED"
                    db.commit()
                elif not row:
                    try:
                        async with httpx.AsyncClient(timeout=5) as client:
                            response = await client.get(f"{settings.central_sync_url}/health")
                        _central_online = response.is_success
                    except Exception:
                        _central_online = False
            finally:
                db.close()
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        await asyncio.sleep(2)


async def _maintenance_loop() -> None:
    while True:
        try:
            db = SessionLocal()
            try:
                for event in db.query(GateEvent).filter(GateEvent.lifecycle == "ACTIVE").all():
                    _evaluate(db, event)
                db.commit()
            except Exception:
                db.rollback()
            finally:
                db.close()
        except asyncio.CancelledError:
            raise
        except Exception:
            pass
        await asyncio.sleep(1)


async def start_entry_services() -> None:
    global _sync_task, _maintenance_task
    if settings.deployment_role == "edge":
        if _maintenance_task is None:
            _maintenance_task = asyncio.create_task(_maintenance_loop())
        if settings.central_sync_url and _sync_task is None:
            _sync_task = asyncio.create_task(_sync_loop())


async def stop_entry_services() -> None:
    global _sync_task, _maintenance_task
    for task in (_sync_task, _maintenance_task):
        if task:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
    _sync_task = None
    _maintenance_task = None
