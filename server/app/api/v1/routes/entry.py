"""Fail-safe, edge-owned gate entry workflow."""

from __future__ import annotations

import asyncio
import hashlib
import json
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
from app.models import Alert, AttendanceLog, ComplianceLog, Device, Gate, GateEvent, PpeDetection, PpeItem, SyncOutbox, Worker, WorkerPpe
from app.services.vision import MAX_FRAME_BYTES, decode_jpeg, infer_frame, vision_lock


router = APIRouter(prefix="/entry", tags=["entry"])
settings = get_settings()
REQUIRED = {"Helmet": "helmet", "Reflective Vest": "vest", "Safety Boots": "boots"}
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


def _frame_evidence(encoded: bytes, detections: list[dict[str, Any]], faces: list[dict[str, Any]]) -> dict[str, Any]:
    image = decode_jpeg(encoded)
    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    luminance = float(np.mean(gray))
    sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
    quality = settings.entry_min_luminance <= luminance <= settings.entry_max_luminance and sharpness >= settings.entry_min_laplacian_variance

    people = [row for row in detections if row["label"].lower() == "person"]
    multiple = len(faces) > 1 or len(people) > 1
    person_box = people[0]["bbox"] if len(people) == 1 else None
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
        matches = []
        if person_box and framing and quality:
            px1, py1, px2, py2 = person_box
            person_height = max(1, py2 - py1)
            for row in detections:
                if row["label"].lower() != label:
                    continue
                x1, y1, x2, y2 = row["bbox"]
                cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
                relative_y = (cy - py1) / person_height
                region_ok = (label == "helmet" and relative_y <= .35) or (label == "vest" and .15 <= relative_y <= .75) or (label == "boots" and relative_y >= .62)
                if px1 <= cx <= px2 and py1 <= cy <= py2 and region_ok:
                    matches.append(row)
        if matches:
            best = max(matches, key=lambda row: row["confidence"])
            visual[item_name] = {"state": "POSITIVE", "confidence": best["confidence"], "bbox": best["bbox"]}
        elif framing and quality:
            visual[item_name] = {"state": "NEGATIVE", "confidence": None, "bbox": None}
        else:
            visual[item_name] = {"state": "UNKNOWN", "confidence": None, "bbox": None}

    return {
        "at": _now().isoformat(), "identity": identity, "multiple": multiple,
        "quality_valid": quality, "framing_valid": framing, "luminance": round(luminance, 1),
        "sharpness": round(sharpness, 1), "visual": visual, "qr_codes": _decode_qr(image),
    }


def _summarize(db: Session, event: GateEvent, state: dict[str, Any]) -> tuple[dict[str, Any], Worker | None]:
    frames = state.get("frames", [])[-WINDOW:]
    matches: dict[str, list[float]] = {}
    for frame in frames:
        identity = frame["identity"]
        if identity["state"] == "MATCH" and identity.get("person_id"):
            matches.setdefault(identity["person_id"], []).append(identity["confidence"])
    candidate = max(matches, key=lambda key: len(matches[key]), default=None)
    worker = None
    if candidate and len(matches[candidate]) >= CONFIRM and not any(frame["multiple"] for frame in frames):
        worker = db.query(Worker).filter(Worker.employee_code.ilike(candidate), Worker.status == "ACTIVE").one_or_none()

    framing_count = sum(frame["framing_valid"] and frame["quality_valid"] for frame in frames)
    visual: dict[str, Any] = {}
    visual_confidences: list[float] = []
    for item in REQUIRED:
        positives = [frame["visual"][item] for frame in frames if frame["visual"][item]["state"] == "POSITIVE"]
        negatives = sum(frame["visual"][item]["state"] == "NEGATIVE" for frame in frames)
        status = "CONFIRMED" if len(positives) >= CONFIRM else "MISSING" if negatives >= CONFIRM else "UNSTABLE"
        confidence = statistics.median([row["confidence"] for row in positives]) if positives else None
        if status == "CONFIRMED" and confidence is not None:
            visual_confidences.append(confidence)
        visual[item] = {"state": status, "positive_frames": len(positives), "negative_frames": negatives, "confidence": confidence}

    qr_counts = Counter(code for frame in frames for code in frame.get("qr_codes", []))
    maximums = state.setdefault("qr_max_counts", {})
    for code, count in qr_counts.items():
        maximums[code] = max(int(maximums.get(code, 0)), count)
    confirmed = state.setdefault("qr_confirmed", {})
    failures = state.setdefault("qr_failures", {})
    if worker:
        for code, count in maximums.items():
            if count < CONFIRM:
                continue
            try:
                normalized = str(uuid.UUID(code))
            except ValueError:
                continue
            assignment = db.get(WorkerPpe, normalized)
            if assignment is None:
                failures[normalized] = {"identifier": normalized, "assignment_result": "UNREGISTERED"}
            elif assignment.worker_id != worker.worker_id:
                failures[normalized] = {"identifier": normalized, "assignment_result": "OTHER_WORKER", "worker_id": assignment.worker_id}
            else:
                confirmed[assignment.ppe_item.name] = {"identifier": normalized, "assignment_result": "MATCH", "worker_id": worker.worker_id}

    assigned_ids: dict[str, set[str]] = {name: set() for name in REQUIRED}
    if worker:
        for assignment in db.query(WorkerPpe).filter(WorkerPpe.worker_id == worker.worker_id).all():
            if assignment.ppe_item.name in assigned_ids:
                assigned_ids[assignment.ppe_item.name].add(assignment.worker_ppe_id)
    qr = {}
    for item in REQUIRED:
        if item in confirmed:
            qr[item] = {"state": "CONFIRMED", **confirmed[item], "max_frames": maximums.get(confirmed[item]["identifier"], 0)}
        else:
            max_seen = max((maximums.get(code, 0) for code in assigned_ids[item]), default=0)
            qr[item] = {"state": "UNSTABLE" if max_seen else "NOT_SEEN", "max_frames": max_seen, "assignment_result": "NOT_SEEN"}

    identity_confidence = statistics.median(matches.get(candidate, [])) * 100 if worker else None
    summary = {
        "identity": {"state": "CONFIRMED" if worker else "UNSTABLE", "supporting_frames": len(matches.get(candidate, [])), "confidence": identity_confidence},
        "framing": {"state": "CONFIRMED" if framing_count >= CONFIRM else "UNSTABLE", "supporting_frames": framing_count},
        "visual": visual, "qr": qr, "qr_failures": list(failures.values()), "frames_in_window": len(frames),
    }
    state["summary"] = summary
    event.identity_confidence = round(identity_confidence, 1) if identity_confidence is not None else None
    visual_support = [max(visual[item]["positive_frames"], visual[item]["negative_frames"]) / WINDOW for item in REQUIRED]
    event.ppe_confidence = round((min(visual_confidences) if len(visual_confidences) == len(REQUIRED) else min(visual_support)) * 100, 1)
    ratios = [len(matches.get(candidate, [])) / WINDOW if candidate else 0, framing_count / WINDOW]
    ratios.extend(max(visual[item]["positive_frames"], visual[item]["negative_frames"]) / WINDOW for item in REQUIRED)
    ratios.extend(min(1, qr[item]["max_frames"] / CONFIRM) for item in REQUIRED)
    event.evidence_confidence = round(min(ratios) * 100, 1)
    return summary, worker


def _finalize(db: Session, event: GateEvent, verdict: str, worker: Worker | None, reasons: list[str], summary: dict[str, Any], state: dict[str, Any]) -> None:
    if event.lifecycle == "FINALIZED":
        return
    now = _now()
    event.lifecycle, event.phase, event.verdict, event.finalized_at = "FINALIZED", "FINAL", verdict, now
    event.worker_id = worker.worker_id if worker else None
    event.reasons_json = _dump(reasons)
    event.qr_results_json = _dump(list(summary["qr"].values()) + summary.get("qr_failures", []))
    event.interventions_json = _dump({
        "barrier": "UNLOCKED" if verdict == "ALLOWED" else "LOCKED",
        "indicator": "GREEN" if verdict == "ALLOWED" else "RED" if verdict == "DENIED" else "AMBER",
        "audible_warning": verdict == "DENIED",
    })
    event.offline_flag = bool(settings.central_sync_url) and not _central_online
    event.sync_status = "PENDING" if settings.central_sync_url else "SYNCED"
    event.evidence_json = _dump(state)

    log = None
    items = db.query(PpeItem).filter(PpeItem.name.in_(REQUIRED)).all()
    item_by_name = {item.name: item for item in items}
    if worker:
        visual_passes = sum(summary["visual"][name]["state"] == "CONFIRMED" for name in REQUIRED)
        qr_passes = sum(summary["qr"][name]["state"] == "CONFIRMED" for name in REQUIRED)
        log = ComplianceLog(
            event_id=event.event_id, final_verdict=verdict, worker_id=worker.worker_id, gate_id=event.gate_id,
            entry_time=event.edge_timestamp, overall_status="COMPLIANT" if verdict == "ALLOWED" else "DENIED" if verdict == "DENIED" else "NON_COMPLIANT",
            compliance_score=round((visual_passes + qr_passes) * 100 / 6, 1), confidence_score=event.evidence_confidence,
            latitude=event.gate_latitude, longitude=event.gate_longitude, offline_flag=event.offline_flag, sync_status=event.sync_status,
        )
        db.add(log)
        db.flush()
        for name in REQUIRED:
            item = item_by_name.get(name)
            if not item:
                continue
            visual = summary["visual"][name]
            qr = summary["qr"][name]
            db.add(PpeDetection(log_id=log.log_id, ppe_id=item.ppe_id, detected=visual["state"] == "CONFIRMED", confidence_score=(visual["confidence"] or 0) * 100 if visual["confidence"] is not None else None, detection_source="AI", evidence_state=visual["state"]))
            db.add(PpeDetection(log_id=log.log_id, ppe_id=item.ppe_id, detected=qr["state"] == "CONFIRMED", confidence_score=min(100, qr["max_frames"] * 100 / CONFIRM), detection_source="QR", evidence_state=qr["state"], observed_identifier=qr.get("identifier"), assignment_result=qr.get("assignment_result")))
        if verdict == "ALLOWED":
            db.add(AttendanceLog(event_id=event.event_id, worker_id=worker.worker_id, gate_id=event.gate_id, entry_time=event.edge_timestamp, status="INSIDE"))

    identity_alert = verdict == "HOLD" and any(reason in reasons for reason in ("UNKNOWN_FACE", "MULTIPLE_IDENTITIES", "MULTIPLE_PERSONS"))
    if verdict == "DENIED" or identity_alert:
        db.add(Alert(
            event_id=event.event_id, gate_id=event.gate_id, log_id=log.log_id if log else None,
            worker_id=worker.worker_id if worker else None,
            alert_type="GATE_COMPLIANCE_DENIED" if verdict == "DENIED" else "GATE_IDENTITY_HOLD",
            severity="CRITICAL" if verdict == "DENIED" else "WARNING",
            message="; ".join(reasons), status="ACTIVE",
        ))

    payload = _event_dict(event)
    payload_json = _dump({"schema_version": 1, "event": payload})
    payload_hash = hashlib.sha256(payload_json.encode()).hexdigest()
    event.payload_hash = payload_hash
    if settings.central_sync_url:
        db.add(SyncOutbox(event_id=event.event_id, payload_json=payload_json, payload_hash=payload_hash, next_retry_at=now))


def _evaluate(db: Session, event: GateEvent, force: bool = False) -> bool:
    if event.lifecycle == "FINALIZED":
        return True
    state = _load(event.evidence_json, {"frames": [], "qr_max_counts": {}, "qr_confirmed": {}, "qr_failures": {}})
    summary, worker = _summarize(db, event, state)
    now = _now()
    if state.get("subject_started_at") and not state.get("identity_deadline"):
        state["identity_deadline"] = (_aware(datetime.fromisoformat(state["subject_started_at"])) + timedelta(seconds=settings.entry_identity_timeout_seconds)).isoformat()
    if worker and event.phase == "IDENTITY":
        event.phase = "EVIDENCE"
        event.worker_id = worker.worker_id
        state["evidence_deadline"] = (now + timedelta(seconds=settings.entry_evidence_timeout_seconds)).isoformat()

    reasons: list[str] = []
    framing_ok = summary["framing"]["state"] == "CONFIRMED"
    if worker and framing_ok:
        for name, value in summary["visual"].items():
            if value["state"] == "MISSING":
                reasons.append(f"{REQUIRED[name].upper()}_VISUALLY_MISSING")
        for failure in summary.get("qr_failures", []):
            reasons.append("PPE_ASSIGNED_TO_OTHER_WORKER" if failure["assignment_result"] == "OTHER_WORKER" else "UNREGISTERED_PPE_QR")
        if reasons:
            _finalize(db, event, "DENIED", worker, sorted(set(reasons)), summary, state)
            return True
        if all(summary["visual"][name]["state"] == "CONFIRMED" and summary["qr"][name]["state"] == "CONFIRMED" for name in REQUIRED):
            _finalize(db, event, "ALLOWED", worker, [], summary, state)
            return True

    identity_deadline = datetime.fromisoformat(state["identity_deadline"]) if state.get("identity_deadline") else None
    evidence_deadline = datetime.fromisoformat(state["evidence_deadline"]) if state.get("evidence_deadline") else None
    expired = (
        event.phase == "EVIDENCE" and evidence_deadline is not None and now >= _aware(evidence_deadline)
    ) or (
        event.phase == "IDENTITY" and identity_deadline is not None and now >= _aware(identity_deadline)
    )
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
        previously_confirmed = db.get(Worker, event.worker_id) if event.worker_id and event.phase == "EVIDENCE" else None
        _finalize(db, event, "HOLD", previously_confirmed, reasons, summary, state)
        return True
    if not framing_ok:
        reasons.append("POOR_FRAMING_OR_IMAGE_QUALITY")
    for name in REQUIRED:
        if summary["visual"][name]["state"] == "UNSTABLE":
            reasons.append(f"{REQUIRED[name].upper()}_VISUAL_UNSTABLE")
        if summary["qr"][name]["state"] == "NOT_SEEN":
            reasons.append(f"{REQUIRED[name].upper()}_QR_MISSING")
        elif summary["qr"][name]["state"] == "UNSTABLE":
            reasons.append(f"{REQUIRED[name].upper()}_QR_UNSTABLE")
    verdict = "DENIED" if framing_ok and any(reason.endswith("_QR_MISSING") for reason in reasons) else "HOLD"
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
    db = SessionLocal()
    try:
        event = db.get(GateEvent, event_id)
        if event is None:
            await websocket.send_json({"type": "error", "message": "Entry attempt not found"})
            return
        await websocket.send_json({"type": "entry_meta", "entry": _event_dict(event)})
    finally:
        db.close()
    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                break
            frame = message.get("bytes")
            if frame is None:
                continue
            if len(frame) > MAX_FRAME_BYTES:
                await websocket.send_json({"type": "error", "message": "Frame is too large"})
                continue
            async with _event_locks.setdefault(event_id, asyncio.Lock()):
                async with vision_lock:
                    output, detections, yolo_ms, faces, face_ms, face_error, _ = await asyncio.to_thread(infer_frame, frame, .5)
                    evidence = await asyncio.to_thread(_frame_evidence, frame, detections, faces)
                db = SessionLocal()
                try:
                    event = db.get(GateEvent, event_id)
                    if event is None:
                        await websocket.send_json({"type": "error", "message": "Entry attempt not found"})
                        return
                    if event.lifecycle == "ACTIVE":
                        state = _load(event.evidence_json, {"frames": []})
                        state.setdefault("frames", []).append(evidence)
                        state["frames"] = state["frames"][-WINDOW:]
                        if not state.get("subject_started_at") and (evidence["identity"]["state"] != "NONE" or any(d["label"].lower() == "person" for d in detections)):
                            state["subject_started_at"] = evidence["at"]
                        event.evidence_json = _dump(state)
                        _evaluate(db, event)
                        db.commit()
                        db.refresh(event)
                    metadata = {"type": "frame_meta", "entry": _event_dict(event), "detections": detections, "faces": faces, "inference_ms": round(yolo_ms, 1), "face_inference_ms": round(face_ms, 1)}
                    if face_error:
                        metadata["face_error"] = face_error
                except Exception:
                    db.rollback()
                    raise
                finally:
                    db.close()
            await websocket.send_json(metadata)
            await websocket.send_bytes(output)
    except (WebSocketDisconnect, RuntimeError):
        pass


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
            raise HTTPException(409, "The event ID already exists with a different payload")
        return {"event_id": event_id, "status": "SYNCED", "duplicate": True}
    worker_data = event_data.get("worker")
    worker = db.get(Worker, worker_data["worker_id"]) if worker_data else None
    gate = db.get(Gate, event_data["gate"]["gate_id"])
    device = db.get(Device, event_data["device"]["device_id"])
    if gate is None or device is None or (worker_data and worker is None):
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
            db.add(PpeDetection(log_id=log.log_id, ppe_id=item.ppe_id, detected=visual.get("state") == "CONFIRMED", confidence_score=(visual.get("confidence") or 0) * 100 if visual.get("confidence") is not None else None, detection_source="AI", evidence_state=visual.get("state")))
            db.add(PpeDetection(log_id=log.log_id, ppe_id=item.ppe_id, detected=qr.get("state") == "CONFIRMED", confidence_score=min(100, qr.get("max_frames", 0) * 100 / CONFIRM), detection_source="QR", evidence_state=qr.get("state"), observed_identifier=qr.get("identifier"), assignment_result=qr.get("assignment_result")))
        if verdict == "ALLOWED":
            db.add(AttendanceLog(event_id=event_id, worker_id=worker.worker_id, gate_id=gate.gate_id, entry_time=event.edge_timestamp, status="INSIDE"))
    if event.verdict == "DENIED" or any(reason in event_data.get("reasons", []) for reason in ("UNKNOWN_FACE", "MULTIPLE_IDENTITIES", "MULTIPLE_PERSONS")):
        db.add(Alert(event_id=event_id, gate_id=gate.gate_id, log_id=log.log_id if log else None, worker_id=worker.worker_id if worker else None, alert_type="GATE_COMPLIANCE_DENIED" if event.verdict == "DENIED" else "GATE_IDENTITY_HOLD", severity="CRITICAL" if event.verdict == "DENIED" else "WARNING", message="; ".join(event_data.get("reasons", [])), status="ACTIVE"))
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
