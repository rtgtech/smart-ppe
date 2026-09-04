"""Deterministic demonstration data for the PPE dashboard.

This module is invoked once for a new demo database. It is deliberately kept
out of normal startup reconciliation so later operator edits are preserved.
"""

from datetime import datetime, time, timedelta, timezone

from sqlalchemy.orm import Session

from app.models import AttendanceLog, ComplianceLog, Gate, PpeDetection, PpeItem, Worker, WorkerPpe


PPE_CATALOG = {
    "Helmet": {
        "description": "Yellow HDPE mining helmet with six-point suspension and adjustable chin strap.",
        "serial_prefix": "HLM",
        "service_days": 1095,
        "source": "AI",
        "miss_every": 47,
    },
    "Safety Boots": {
        "description": "Ankle-height leather safety boots with steel toe, puncture-resistant midsole, and anti-slip sole.",
        "serial_prefix": "BTS",
        "service_days": 365,
        "source": "AI",
        "miss_every": 31,
    },
    "Reflective Vest": {
        "description": "Fluorescent lime work vest with 50 mm reflective tape for low-light underground visibility.",
        "serial_prefix": "VST",
        "service_days": 365,
        "source": "AI",
        "miss_every": 13,
    },
}


def seed_ppe_demo_data(db: Session, history_days: int = 30) -> None:
    """Populate realistic PPE inventory and recent detection history."""
    workers = db.query(Worker).order_by(Worker.worker_id).limit(4).all()
    gate = db.query(Gate).order_by(Gate.gate_id).first()
    all_items = db.query(PpeItem).all()
    items = {item.name: item for item in all_items if item.name in PPE_CATALOG}
    if not workers or gate is None or len(items) != len(PPE_CATALOG):
        return

    today = datetime.now(timezone.utc).date()
    selected_worker_ids = {worker.worker_id for worker in workers}
    selected_item_ids = {item.ppe_id for item in items.values()}

    # Reconcile data from older demo catalogs without touching live gate logs.
    demo_logs = db.query(ComplianceLog).filter(ComplianceLog.image_url.like("seed://ppe-history/%")).all()
    for log in demo_logs:
        if log.worker_id not in selected_worker_ids:
            db.query(AttendanceLog).filter(
                AttendanceLog.worker_id == log.worker_id,
                AttendanceLog.gate_id == log.gate_id,
                AttendanceLog.entry_time == log.entry_time,
            ).delete(synchronize_session=False)
            db.delete(log)
            continue

        db.query(PpeDetection).filter(
            PpeDetection.log_id == log.log_id,
            PpeDetection.ppe_id.notin_(selected_item_ids),
        ).delete(synchronize_session=False)
        remaining = db.query(PpeDetection).filter(PpeDetection.log_id == log.log_id).all()
        if remaining:
            detected_count = sum(row.detected for row in remaining)
            log.compliance_score = round(detected_count * 100 / len(remaining), 1)
            log.confidence_score = round(sum(row.confidence_score or 0 for row in remaining) / len(remaining), 1)
            log.overall_status = "COMPLIANT" if detected_count == len(remaining) else "DENIED"

    db.flush()

    for item in all_items:
        if item.name in PPE_CATALOG:
            db.query(WorkerPpe).filter(
                WorkerPpe.ppe_id == item.ppe_id,
                WorkerPpe.worker_id.notin_(selected_worker_ids),
            ).delete(synchronize_session=False)
            continue
        db.query(PpeDetection).filter(PpeDetection.ppe_id == item.ppe_id).delete(synchronize_session=False)
        db.query(WorkerPpe).filter(WorkerPpe.ppe_id == item.ppe_id).delete(synchronize_session=False)
        db.delete(item)

    db.flush()

    for item_name, details in PPE_CATALOG.items():
        item = items[item_name]
        item.description = details["description"]

        for worker_index, worker in enumerate(workers):
            assignment = (
                db.query(WorkerPpe)
                .filter(
                    WorkerPpe.worker_id == worker.worker_id,
                    WorkerPpe.ppe_id == item.ppe_id,
                    WorkerPpe.status == "ACTIVE",
                )
                .first()
            )
            issued_at = datetime.combine(
                today - timedelta(days=45 + worker_index * 17 + item.ppe_id * 9),
                time(9, 0),
                timezone.utc,
            )
            serial_number = f"{details['serial_prefix']}-{today.year % 100:02d}-{worker.employee_code[-5:]}"
            rfid_tag = f"E200-{item.ppe_id:02d}-{worker.employee_code[-5:]}"
            expiry_date = issued_at.date() + timedelta(days=details["service_days"])

            if assignment is None:
                assignment = WorkerPpe(
                    worker_id=worker.worker_id,
                    ppe_id=item.ppe_id,
                    status="ACTIVE",
                )
                db.add(assignment)

            assignment.serial_number = serial_number
            assignment.rfid_tag = rfid_tag
            assignment.issued_at = issued_at
            assignment.expiry_date = expiry_date

    db.flush()

    ordered_items = [items[name] for name in PPE_CATALOG]
    for day_offset in range(history_days):
        check_date = today - timedelta(days=day_offset)
        for worker_index, worker in enumerate(workers):
            marker = f"seed://ppe-history/{check_date.isoformat()}/{worker.employee_code}"
            existing = db.query(ComplianceLog).filter(ComplianceLog.image_url == marker).first()
            if existing is not None:
                continue

            shift_hour = 6 if worker_index % 2 == 0 else 14
            entry_time = datetime.combine(
                check_date,
                time(shift_hour, 5 + worker_index * 7),
                timezone.utc,
            )
            sample_number = day_offset * len(workers) + worker_index
            detection_rows = []
            for item in ordered_items:
                details = PPE_CATALOG[item.name]
                detected = (sample_number + item.ppe_id * 7) % details["miss_every"] != 0
                confidence = (
                    89.0 + ((sample_number * 3 + item.ppe_id * 2) % 10)
                    if detected
                    else 42.0 + ((sample_number + item.ppe_id) % 18)
                )
                detection_rows.append((item, details, detected, confidence))

            detected_count = sum(row[2] for row in detection_rows)
            compliance_score = round(detected_count * 100 / len(detection_rows), 1)
            log = ComplianceLog(
                worker_id=worker.worker_id,
                gate_id=gate.gate_id,
                entry_time=entry_time,
                overall_status="COMPLIANT" if detected_count == len(detection_rows) else "DENIED",
                compliance_score=compliance_score,
                confidence_score=round(sum(row[3] for row in detection_rows) / len(detection_rows), 1),
                image_url=marker,
                latitude=23.7957,
                longitude=86.4304,
                offline_flag=day_offset % 11 == 0 and worker_index == 3,
                sync_status="SYNCED",
            )
            db.add(log)
            db.flush()

            for item, details, detected, confidence in detection_rows:
                db.add(PpeDetection(
                    log_id=log.log_id,
                    ppe_id=item.ppe_id,
                    detected=detected,
                    confidence_score=confidence,
                    bounding_box="[124, 68, 302, 418]" if details["source"] == "AI" and detected else None,
                    detection_source=details["source"],
                ))

            attendance_exists = (
                db.query(AttendanceLog)
                .filter(
                    AttendanceLog.worker_id == worker.worker_id,
                    AttendanceLog.gate_id == gate.gate_id,
                    AttendanceLog.entry_time == entry_time,
                )
                .first()
            )
            if attendance_exists is None:
                db.add(AttendanceLog(
                    worker_id=worker.worker_id,
                    gate_id=gate.gate_id,
                    entry_time=entry_time,
                    exit_time=entry_time + timedelta(hours=8) if check_date < today else None,
                    status="OUTSIDE" if check_date < today or detected_count < len(detection_rows) else "INSIDE",
                ))
