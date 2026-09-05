"""Durably persist a finalized camera entry decision exactly once."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.audit import create_audit_log
from app.core.config import get_settings
from app.models import Alert, AttendanceLog, ComplianceLog, Device, GateEvent, PpeDetection, PpeItem, Worker
from app.services.entry_pipeline import EntrySession


PPE_STORAGE_NAMES = {"Helmet": "Helmet", "Vest": "Vest", "Boots": "Shoes"}


def _worker_for_session(db: Session, session: EntrySession) -> Worker | None:
    employee_code = (session.worker or {}).get("employee_code")
    if not employee_code:
        return None
    return (
        db.query(Worker)
        .filter(func.lower(Worker.employee_code) == employee_code.lower())
        .one_or_none()
    )


def persist_entry_session(db: Session, session: EntrySession) -> GateEvent:
    """Persist a finalized session and its derived records in one transaction."""
    if session.lifecycle != "FINALIZED" or session.verdict is None:
        raise ValueError("Only finalized entry sessions can be persisted")

    existing = db.get(GateEvent, session.id)
    if existing is not None:
        session.mark_persisted()
        return existing

    settings = get_settings()
    device = db.query(Device).filter(Device.serial_number == settings.edge_device_serial).one_or_none()
    if device is None or device.gate is None:
        raise RuntimeError(f"Entry device '{settings.edge_device_serial}' is not configured")
    gate = device.gate
    if gate.latitude is None or gate.longitude is None:
        raise RuntimeError(f"Gate '{gate.name}' requires latitude and longitude")

    worker = _worker_for_session(db, session)
    result = session.result()
    visual = result["evidence"]["visual"]
    now = datetime.now(timezone.utc)
    event = GateEvent(
        event_id=session.id,
        worker_id=worker.worker_id if worker else None,
        gate_id=gate.gate_id,
        device_id=device.device_id,
        lifecycle="FINALIZED",
        verdict=session.verdict,
        gate_latitude=gate.latitude,
        gate_longitude=gate.longitude,
        edge_timestamp=now,
        finalized_at=now,
        evidence_confidence=result["evidence_confidence"],
        reasons_json=json.dumps(session.reasons, separators=(",", ":")),
        evidence_json=json.dumps({"summary": result["evidence"]}, separators=(",", ":")),
        qr_results_json="[]",
        offline_flag=False,
        sync_status="SYNCED",
    )
    db.add(event)

    compliance = None
    if worker is not None:
        decided = [row for row in visual.values() if row["state"] in {"CONFIRMED", "MISSING"}]
        confirmed = sum(row["state"] == "CONFIRMED" for row in decided)
        compliance_score = round(confirmed * 100 / len(visual), 1) if visual else 0.0
        overall_status = {
            "ALLOWED": "COMPLIANT",
            "DENIED": "DENIED",
            "HOLD": "NON_COMPLIANT",
        }[session.verdict]
        compliance = ComplianceLog(
            event_id=session.id,
            final_verdict=session.verdict,
            worker_id=worker.worker_id,
            gate_id=gate.gate_id,
            entry_time=now,
            overall_status=overall_status,
            compliance_score=compliance_score,
            confidence_score=result["evidence_confidence"],
            offline_flag=False,
            sync_status="SYNCED",
            data_origin="LIVE",
        )
        db.add(compliance)
        db.flush()

        stored_items = {
            item.name: item
            for item in db.query(PpeItem).filter(PpeItem.name.in_(PPE_STORAGE_NAMES.values())).all()
        }
        missing_configuration = set(PPE_STORAGE_NAMES.values()) - set(stored_items)
        if missing_configuration:
            raise RuntimeError(f"Missing PPE configuration: {', '.join(sorted(missing_configuration))}")
        for display_name, row in visual.items():
            if row["state"] not in {"CONFIRMED", "MISSING"}:
                continue
            item = stored_items[PPE_STORAGE_NAMES[display_name]]
            db.add(PpeDetection(
                log_id=compliance.log_id,
                ppe_id=item.ppe_id,
                detected=row["state"] == "CONFIRMED",
                confidence_score=row["confidence"],
                detection_source="AI",
            ))

        if session.verdict == "ALLOWED":
            open_attendance = (
                db.query(AttendanceLog)
                .filter(AttendanceLog.worker_id == worker.worker_id, AttendanceLog.exit_time.is_(None))
                .first()
            )
            if open_attendance is None:
                db.add(AttendanceLog(
                    event_id=session.id,
                    worker_id=worker.worker_id,
                    gate_id=gate.gate_id,
                    entry_time=now,
                    status="INSIDE",
                    data_origin="LIVE",
                ))

    if session.verdict in {"DENIED", "HOLD"}:
        severity = "CRITICAL" if session.verdict == "DENIED" else "WARNING"
        message = ", ".join(reason.replace("_", " ").title() for reason in session.reasons) or "Entry requires review"
        db.add(Alert(
            event_id=session.id,
            gate_id=gate.gate_id,
            log_id=compliance.log_id if compliance else None,
            worker_id=worker.worker_id if worker else None,
            alert_type="PPE_ENTRY_DECISION",
            severity=severity,
            message=message,
            status="ACTIVE",
        ))

    create_audit_log(
        db,
        category="GATE_EVENT",
        action="GATE_FINALIZED",
        status=session.verdict,
        message=f"Entry decision finalized at {gate.name}",
        event_id=session.id,
        worker_id=worker.worker_id if worker else None,
        gate_id=gate.gate_id,
        metadata={"reasons": session.reasons, "compliance_score": compliance.compliance_score if compliance else None},
    )

    try:
        db.commit()
    except Exception:
        db.rollback()
        existing = db.get(GateEvent, session.id)
        if existing is None:
            raise
        event = existing
    session.mark_persisted()
    return event
