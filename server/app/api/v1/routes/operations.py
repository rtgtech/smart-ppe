"""REST resources and read models used by the operational frontend."""

from __future__ import annotations

import calendar
import io
import json
import logging
from datetime import date as date_type, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.core.audit import create_audit_log
from app.services.report_pdf import generate_all_employees_report, generate_employee_report
from app.models import (
    Alert,
    AttendanceLog,
    ComplianceLog,
    Department,
    Device,
    Gate,
    GateEvent,
    Mine,
    PpeDetection,
    PpeItem,
    Report,
    SafetyScore,
    Worker,
)
from app.schemas.alert import AlertCreate, AlertUpdate
from app.schemas.attendance_log import AttendanceLogCreate, AttendanceLogUpdate
from app.schemas.compliance_log import ComplianceLogCreate, ComplianceLogUpdate
from app.schemas.device import DeviceCreate, DeviceUpdate
from app.schemas.department import DepartmentCreate, DepartmentUpdate
from app.schemas.gate import GateCreate, GateUpdate
from app.schemas.mine import MineCreate, MineUpdate
from app.schemas.ppe_item import PpeItemCreate, PpeItemUpdate
from app.schemas.report import ReportCreate, ReportUpdate
from app.services.workers import latest_safety_score


router = APIRouter(tags=["operations"])
logger = logging.getLogger(__name__)


class StatusPatch(BaseModel):
    status: str


def _date_filters(query, model, selected_date: date_type | None, shift: str | None, gate_id: int | None, worker: str | None = None):
    if selected_date:
        query = query.filter(func.date(model.entry_time) == str(selected_date))
    if gate_id:
        query = query.filter(model.gate_id == gate_id)
    if worker:
        query = query.join(Worker, Worker.worker_id == model.worker_id)
        query = query.filter((Worker.name.ilike(f"%{worker}%")) | (Worker.employee_code.ilike(f"%{worker}%")))
    return query


def _query_filters(date: str | None, shift: str | None, gate_id: int | None):
    try:
        selected = datetime.strptime(date, "%Y-%m-%d").date() if date else None
    except ValueError:
        raise HTTPException(400, "date must be YYYY-MM-DD")
    return selected, shift.upper() if shift and shift.upper() != "ALL" else None, gate_id


def _date_label(value: datetime | None) -> str:
    if value is None:
        return "—"
    return value.strftime("%d %b, %H:%M")


def _format_iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.strftime("%Y-%m-%dT%H:%M:%S")


def _gate_row(db: Session, gate: Gate) -> dict:
    workers = (
        db.query(func.count(func.distinct(AttendanceLog.worker_id)))
        .filter(AttendanceLog.gate_id == gate.gate_id, AttendanceLog.status.in_(["PRESENT", "INSIDE"]))
        .scalar()
        or 0
    )
    denials = (
        db.query(func.count(ComplianceLog.log_id))
        .filter(ComplianceLog.gate_id == gate.gate_id, ComplianceLog.overall_status == "DENIED")
        .scalar()
        or 0
    )
    return {
        "gate_id": gate.gate_id,
        "id": f"G{gate.gate_id:02d}",
        "name": gate.name,
        "label": gate.location,
        "status": gate.status,
        "workers": workers,
        "denials": denials,
    }


def _device_row(device: Device) -> dict:
    heartbeat = _date_label(device.last_seen)
    return {
        "device_id": device.device_id,
        "id": device.serial_number,
        "type": device.device_type.replace("_", " "),
        "device_type": device.device_type,
        "gate_id": device.gate_id,
        "gate": device.gate.name if device.gate else "",
        "status": device.status,
        "heartbeat": heartbeat,
        "last_seen": device.last_seen,
        "battery_level": device.battery_level,
        "firmware_version": device.firmware_version,
    }


def _alert_row(alert: Alert) -> dict:
    return {
        "alert_id": alert.alert_id,
        "id": f"AL-{alert.alert_id:04d}",
        "severity": alert.severity,
        "title": alert.alert_type,
        "worker_id": alert.worker_id,
        "worker": alert.worker.name if alert.worker else "—",
        "detail": alert.message,
        "gate": alert.gate.name if alert.gate else alert.compliance_log.gate.name if alert.compliance_log and alert.compliance_log.gate else "—",
        "time": _date_label(alert.created_at),
        "status": alert.status,
        "officer": "—",
        "resolved_at": alert.resolved_at,
    }


def _attendance_row(log: AttendanceLog, db: Session | None = None) -> dict:
    ppe_status = "VERIFIED"
    if db is not None:
        compliance = (
            db.query(ComplianceLog)
            .filter(
                ComplianceLog.worker_id == log.worker_id,
                ComplianceLog.gate_id == log.gate_id,
                ComplianceLog.entry_time >= log.entry_time - timedelta(minutes=30),
                ComplianceLog.entry_time <= log.entry_time + timedelta(minutes=30),
            )
            .order_by(ComplianceLog.entry_time.desc())
            .first()
        )
        if compliance:
            ppe_status = "VERIFIED" if compliance.overall_status == "COMPLIANT" else "FLAGGED" if compliance.overall_status == "WARNING" else "DENIED"

    return {
        "attendance_id": log.attendance_id,
        "worker_id": log.worker_id,
        "worker": log.worker.name if log.worker else "Unknown",
        "workerId": log.worker.employee_code if log.worker else "—",
        "department": log.worker.department.name if log.worker and log.worker.department else "Unassigned",
        "gate_id": log.gate_id,
        "gate": log.gate.name if log.gate else "—",
        "location": log.gate.location if log.gate else "Main Shaft Entry",
        "entry": _format_iso(log.entry_time),
        "exit": _format_iso(log.exit_time),
        "ppe": ppe_status,
        "status": "UNDERGROUND" if log.status in ["INSIDE", "PRESENT"] and not log.exit_time else "EXITED",
        "raw_status": log.status,
    }


def _compliance_row(log: ComplianceLog, db: Session | None = None) -> dict:
    event = db.get(GateEvent, log.event_id) if db is not None and log.event_id else None
    row = {
        "log_id": log.log_id,
        "id": log.event_id or f"EVT-{log.log_id:05d}",
        "eventId": log.event_id or f"EVT-{log.log_id:05d}",
        "time": _format_iso(log.entry_time),
        "worker": log.worker.name if log.worker else "Unknown",
        "workerId": log.worker.employee_code if log.worker else "—",
        "gate": log.gate.name if log.gate else "—",
        "decision": log.final_verdict or {"COMPLIANT": "ALLOWED", "NON_COMPLIANT": "WARNING", "DENIED": "DENIED"}.get(log.overall_status, log.overall_status),
        "source": "YOLO + SFACE + OPENCV QR" if log.event_id else "AI CAMERA",
        "compliance_score": log.compliance_score,
        "confidence_score": log.confidence_score,
        "offline": log.offline_flag,
        "sync_status": log.sync_status,
        "type": "PPE verification",
        "status": log.sync_status.title() if log.sync_status else "Synced",
    }
    if event:
        row.update({
            "device_id": event.device_id,
            "latitude": event.gate_latitude,
            "longitude": event.gate_longitude,
            "edge_timestamp": _format_iso(event.edge_timestamp),
            "reasons": json.loads(event.reasons_json),
            "qr_results": json.loads(event.qr_results_json),
            "evidence": json.loads(event.evidence_json).get("summary", {}),
        })
    return row


def _gate_event_row(event: GateEvent) -> dict:
    return {
        "id": event.event_id, "eventId": event.event_id, "time": _format_iso(event.edge_timestamp),
        "worker": event.worker.name if event.worker else "Unknown", "workerId": event.worker.employee_code if event.worker else "—",
        "gate": event.gate.name if event.gate else "—", "decision": event.verdict, "source": "YOLO + SFACE + OPENCV QR",
        "confidence_score": event.evidence_confidence, "offline": event.offline_flag, "sync_status": event.sync_status,
        "type": "Gate entry", "status": event.sync_status.title(), "device_id": event.device_id,
        "latitude": event.gate_latitude, "longitude": event.gate_longitude,
        "reasons": json.loads(event.reasons_json), "qr_results": json.loads(event.qr_results_json),
        "evidence": json.loads(event.evidence_json).get("summary", {}),
    }


def _report_row(report: Report, db: Session) -> dict:
    worker = db.get(Worker, report.generated_by) if report.generated_by else None

    # Calculate actual compliance event records in this period from db
    comp_count = db.query(func.count(ComplianceLog.log_id)).filter(
        func.date(ComplianceLog.entry_time) >= str(report.period_start),
        func.date(ComplianceLog.entry_time) <= str(report.period_end),
    )
    if report.generated_by:
        comp_count = comp_count.filter(ComplianceLog.worker_id == report.generated_by)
    records_count = comp_count.scalar() or 0

    file_name = report.file_url or ""
    is_all = "All_Employees" in file_name or "ALL_EMPLOYEES" in file_name.upper()
    is_employee = bool((worker or ("Employee_" in file_name)) and not is_all)
    period_name = "Monthly" if "MONTHLY" in (report.report_type or "").upper() or "Monthly" in file_name else "Weekly"

    if is_employee and worker:
        name = f"{period_name} Employee Safety Audit — {worker.name} ({worker.employee_code})"
        scope = "Individual Employee"
        target = f"{worker.name} ({worker.employee_code})"
    elif is_employee and "Employee_" in file_name:
        parts = file_name.replace(".pdf", "").split("_")
        code = parts[3] if len(parts) > 3 else "Worker"
        name = f"{period_name} Employee Safety Audit ({code})"
        scope = "Individual Employee"
        target = code
    else:
        name = f"{period_name} Workforce Safety & Compliance Roster"
        scope = "All Employees"
        target = "Mine-Wide Workforce"

    download_url = f"/reports/{report.report_id}/download"
    gen_time_str = report.generated_at.strftime("%d %b %Y, %H:%M") if report.generated_at else "—"

    return {
        "report_id": report.report_id,
        "id": f"RPT-{report.report_id:04d}",
        "name": name,
        "report_type": period_name.upper(),
        "scope": scope,
        "target": target,
        "description": f"Audit-ready {period_name.lower()} report covering {report.period_start.strftime('%d %b %Y')} to {report.period_end.strftime('%d %b %Y')}",
        "date": report.period_end.strftime("%Y-%m-%d"),
        "period_start": str(report.period_start),
        "period_end": str(report.period_end),
        "period_label": f"{report.period_start.strftime('%d %b %Y')} – {report.period_end.strftime('%d %b %Y')}",
        "lastGenerated": gen_time_str,
        "records": records_count,
        "status": "READY",
        "file_url": report.file_url,
        "download_url": download_url,
    }


@router.get("/mines")
def list_mines(db: Session = Depends(get_db)):
    return db.query(Mine).order_by(Mine.name).all()


@router.post("/mines", status_code=status.HTTP_201_CREATED)
def create_mine(payload: MineCreate, db: Session = Depends(get_db)):
    mine = Mine(**payload.model_dump())
    db.add(mine)
    db.commit()
    db.refresh(mine)
    return mine


@router.get("/mines/{mine_id}")
def get_mine(mine_id: int, db: Session = Depends(get_db)):
    mine = db.get(Mine, mine_id)
    if mine is None:
        raise HTTPException(404, "Mine not found")
    return mine


@router.delete("/mines/{mine_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_mine(mine_id: int, db: Session = Depends(get_db)):
    mine = db.get(Mine, mine_id)
    if mine is None:
        raise HTTPException(404, "Mine not found")
    db.delete(mine)
    db.commit()
    return Response(status_code=204)


@router.patch("/mines/{mine_id}")
def update_mine(mine_id: int, payload: MineUpdate, db: Session = Depends(get_db)):
    mine = db.get(Mine, mine_id)
    if mine is None:
        raise HTTPException(404, "Mine not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(mine, field, value)
    db.commit()
    db.refresh(mine)
    return mine


@router.get("/departments")
def list_departments(db: Session = Depends(get_db)):
    return db.query(Department).order_by(Department.name).all()


@router.post("/departments", status_code=status.HTTP_201_CREATED)
def create_department(payload: DepartmentCreate, db: Session = Depends(get_db)):
    department = Department(**payload.model_dump())
    db.add(department)
    db.commit()
    db.refresh(department)
    return department


@router.get("/departments/{department_id}")
def get_department(department_id: int, db: Session = Depends(get_db)):
    department = db.get(Department, department_id)
    if department is None:
        raise HTTPException(404, "Department not found")
    return department


@router.patch("/departments/{department_id}")
def update_department(department_id: int, payload: DepartmentUpdate, db: Session = Depends(get_db)):
    department = db.get(Department, department_id)
    if department is None:
        raise HTTPException(404, "Department not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(department, field, value)
    db.commit()
    db.refresh(department)
    return department


@router.delete("/departments/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_department(department_id: int, db: Session = Depends(get_db)):
    department = db.get(Department, department_id)
    if department is None:
        raise HTTPException(404, "Department not found")
    db.delete(department)
    db.commit()
    return Response(status_code=204)


@router.get("/gates")
def list_gates(db: Session = Depends(get_db)):
    return [_gate_row(db, gate) for gate in db.query(Gate).order_by(Gate.name).all()]


@router.get("/gates/violations")
def gate_violations(db: Session = Depends(get_db)):
    return [{"gate": row[0], "denials": row[1]} for row in db.query(Gate.name, func.count(ComplianceLog.log_id)).outerjoin(ComplianceLog, ComplianceLog.gate_id == Gate.gate_id).filter(ComplianceLog.overall_status == "DENIED").group_by(Gate.gate_id).order_by(Gate.name).all()]


@router.post("/gates", status_code=status.HTTP_201_CREATED)
def create_gate(payload: GateCreate, db: Session = Depends(get_db)):
    gate = Gate(**payload.model_dump())
    db.add(gate)
    db.commit()
    db.refresh(gate)
    return _gate_row(db, gate)


@router.patch("/gates/{gate_id}")
def update_gate(gate_id: int, payload: GateUpdate, db: Session = Depends(get_db)):
    gate = db.get(Gate, gate_id)
    if gate is None:
        raise HTTPException(404, "Gate not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(gate, field, value)
    db.commit()
    db.refresh(gate)
    return _gate_row(db, gate)


@router.get("/gates/{gate_id}")
def get_gate(gate_id: int, db: Session = Depends(get_db)):
    gate = db.get(Gate, gate_id)
    if gate is None:
        raise HTTPException(404, "Gate not found")
    return _gate_row(db, gate)


@router.delete("/gates/{gate_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_gate(gate_id: int, db: Session = Depends(get_db)):
    gate = db.get(Gate, gate_id)
    if gate is None:
        raise HTTPException(404, "Gate not found")
    db.delete(gate)
    db.commit()
    return Response(status_code=204)


@router.get("/devices")
def list_devices(db: Session = Depends(get_db)):
    return [_device_row(device) for device in db.query(Device).order_by(Device.serial_number).all()]


@router.post("/devices", status_code=status.HTTP_201_CREATED)
def create_device(payload: DeviceCreate, db: Session = Depends(get_db)):
    device = Device(**payload.model_dump())
    db.add(device)
    db.commit()
    db.refresh(device)
    return _device_row(device)


@router.patch("/devices/{device_id}")
def update_device(device_id: int, payload: DeviceUpdate, db: Session = Depends(get_db)):
    device = db.get(Device, device_id)
    if device is None:
        raise HTTPException(404, "Device not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(device, field, value)
    db.commit()
    db.refresh(device)
    return _device_row(device)


@router.get("/devices/{device_id}")
def get_device(device_id: int, db: Session = Depends(get_db)):
    device = db.get(Device, device_id)
    if device is None:
        raise HTTPException(404, "Device not found")
    return _device_row(device)


@router.delete("/devices/{device_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_device(device_id: int, db: Session = Depends(get_db)):
    device = db.get(Device, device_id)
    if device is None:
        raise HTTPException(404, "Device not found")
    db.delete(device)
    db.commit()
    return Response(status_code=204)


@router.get("/ppe/items")
def list_ppe_items(db: Session = Depends(get_db)):
    return db.query(PpeItem).order_by(PpeItem.ppe_id).all()


@router.get("/ppe/summary")
def ppe_summary(date: str | None = None, shift: str | None = None, gate_id: int | None = None, worker: str | None = None, db: Session = Depends(get_db)):
    selected, shift, gate_id = _query_filters(date, shift, gate_id)
    items = db.query(PpeItem).order_by(PpeItem.ppe_id).all()
    rows = []
    for item in items:
        query = db.query(PpeDetection).join(ComplianceLog, PpeDetection.log_id == ComplianceLog.log_id).filter(PpeDetection.ppe_id == item.ppe_id, PpeDetection.detection_source == "AI", ComplianceLog.overall_status.in_(["COMPLIANT", "DENIED"]))
        current = _date_filters(query, ComplianceLog, selected, shift, gate_id, worker)
        total = current.with_entities(func.count(PpeDetection.detection_id)).scalar() or 0
        detected = current.filter(PpeDetection.detected.is_(True)).with_entities(func.count(PpeDetection.detection_id)).scalar() or 0
        compliance = round(detected * 100 / total, 1) if total else None

        trend = None
        if selected and total:
            previous = _date_filters(query, ComplianceLog, selected - timedelta(days=1), shift, gate_id, worker)
            previous_total = previous.with_entities(func.count(PpeDetection.detection_id)).scalar() or 0
            previous_detected = previous.filter(PpeDetection.detected.is_(True)).with_entities(func.count(PpeDetection.detection_id)).scalar() or 0
            if previous_total:
                trend = round(compliance - (previous_detected * 100 / previous_total), 1)

        rows.append({
            "key": item.name.lower().replace(" ", ""),
            "label": item.name,
            "compliance": compliance,
            "trend": trend,
            "violations": total - detected,
            "is_mandatory": item.is_mandatory,
        })
    return rows


@router.get("/ppe/trend")
def ppe_trend(date: str | None = None, shift: str | None = None, gate_id: int | None = None, worker: str | None = None, db: Session = Depends(get_db)):
    selected, shift, gate_id = _query_filters(date, shift, gate_id)
    since = datetime.now(timezone.utc) - timedelta(days=30) if not selected else datetime.combine(selected, datetime.min.time(), timezone.utc)
    query = db.query(func.date(ComplianceLog.entry_time).label("day"), func.avg(ComplianceLog.compliance_score).label("compliance")).filter(ComplianceLog.entry_time >= since)
    query = _date_filters(query, ComplianceLog, selected, shift, gate_id, worker)
    rows = query.group_by(func.date(ComplianceLog.entry_time)).order_by("day").all()
    return [{"day": str(row.day), "compliance": round(float(row.compliance), 1)} for row in rows]


@router.get("/ppe/violations")
def common_ppe_violations(date: str | None = None, shift: str | None = None, gate_id: int | None = None, worker: str | None = None, db: Session = Depends(get_db)):
    selected, shift, gate_id = _query_filters(date, shift, gate_id)
    query = db.query(PpeItem.name, func.count(PpeDetection.detection_id)).join(PpeDetection, PpeDetection.ppe_id == PpeItem.ppe_id).join(ComplianceLog, PpeDetection.log_id == ComplianceLog.log_id).filter(PpeDetection.detected.is_(False), ComplianceLog.overall_status == "DENIED")
    query = _date_filters(query, ComplianceLog, selected, shift, gate_id, worker)
    totals = query.group_by(PpeItem.name).order_by(func.count(PpeDetection.detection_id).desc()).all()
    total = sum(value for _, value in totals)
    return [{"label": name, "pct": round(value * 100 / total, 1) if total else 0, "violations": value} for name, value in totals]


@router.get("/ppe/config")
def ppe_config(db: Session = Depends(get_db)):
    return [{"key": item.name.lower().replace(" ", ""), "label": item.name, "state": "REQUIRED" if item.is_mandatory else "OPTIONAL", "ppe_id": item.ppe_id} for item in db.query(PpeItem).order_by(PpeItem.ppe_id).all()]


@router.post("/ppe/items", status_code=status.HTTP_201_CREATED)
def create_ppe_item(payload: PpeItemCreate, db: Session = Depends(get_db)):
    item = PpeItem(**payload.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get("/ppe/items/{ppe_id}")
def get_ppe_item(ppe_id: int, db: Session = Depends(get_db)):
    item = db.get(PpeItem, ppe_id)
    if item is None:
        raise HTTPException(404, "PPE item not found")
    return item


@router.patch("/ppe/items/{ppe_id}")
def update_ppe_item(ppe_id: int, payload: PpeItemUpdate, db: Session = Depends(get_db)):
    item = db.get(PpeItem, ppe_id)
    if item is None:
        raise HTTPException(404, "PPE item not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/ppe/items/{ppe_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_ppe_item(ppe_id: int, db: Session = Depends(get_db)):
    item = db.get(PpeItem, ppe_id)
    if item is None:
        raise HTTPException(404, "PPE item not found")
    db.delete(item)
    db.commit()
    return Response(status_code=204)


class CheckInRequest(BaseModel):
    worker_id: int | None = None
    employee_code: str | None = None
    gate_id: int
    entry_time: str | datetime | None = None


@router.get("/attendance")
def list_attendance(limit: int = Query(500, ge=1, le=5000), date: str | None = None, shift: str | None = None, gate_id: int | None = None, worker: str | None = None, db: Session = Depends(get_db)):
    selected, shift, gate_id = _query_filters(date, shift, gate_id)
    logs = _date_filters(db.query(AttendanceLog), AttendanceLog, selected, shift, gate_id, worker).order_by(AttendanceLog.entry_time.desc()).limit(limit).all()
    return [_attendance_row(log, db) for log in logs]


@router.get("/attendance/kpi")
def attendance_kpi(date: str | None = None, shift: str | None = None, gate_id: int | None = None, worker: str | None = None, db: Session = Depends(get_db)):
    selected, shift, gate_id = _query_filters(date, shift, gate_id)
    selected = selected or datetime.now().date()
    query = _date_filters(db.query(AttendanceLog), AttendanceLog, selected, shift, gate_id, worker)
    entered = query.with_entities(func.count(AttendanceLog.attendance_id)).scalar() or 0
    exited = query.filter(func.date(AttendanceLog.exit_time) == str(selected)).with_entities(func.count(AttendanceLog.attendance_id)).scalar() or 0
    underground = query.filter(AttendanceLog.status.in_(["PRESENT", "INSIDE"]), AttendanceLog.exit_time.is_(None)).with_entities(func.count(func.distinct(AttendanceLog.worker_id))).scalar() or 0
    missing = query.filter(AttendanceLog.exit_time.is_(None), func.date(AttendanceLog.entry_time) < str(selected)).with_entities(func.count(AttendanceLog.attendance_id)).scalar() or 0
    return {"enteredToday": entered, "exitedToday": exited, "currentlyUnderground": underground, "missingExitScans": missing}


@router.get("/attendance/zones")
def attendance_zones(date: str | None = None, shift: str | None = None, gate_id: int | None = None, worker: str | None = None, db: Session = Depends(get_db)):
    selected, shift, gate_id = _query_filters(date, shift, gate_id)
    all_gates = db.query(Gate).all()
    zone_counts: dict[str, int] = {gate.location: 0 for gate in all_gates}
    query = db.query(Gate.location, func.count(func.distinct(AttendanceLog.worker_id))).join(AttendanceLog, AttendanceLog.gate_id == Gate.gate_id).filter(AttendanceLog.status.in_(["PRESENT", "INSIDE"]), AttendanceLog.exit_time.is_(None))
    query = _date_filters(query, AttendanceLog, selected, shift, gate_id, worker)
    rows = query.group_by(Gate.location).all()
    for location, count in rows:
        zone_counts[location] = count
    return [{"zone": location, "count": count} for location, count in zone_counts.items()]


@router.post("/attendance/check-in", status_code=status.HTTP_201_CREATED)
def check_in_worker(payload: CheckInRequest, db: Session = Depends(get_db)):
    if payload.worker_id:
        worker = db.get(Worker, payload.worker_id)
    elif payload.employee_code:
        worker = db.query(Worker).filter(func.lower(Worker.employee_code) == payload.employee_code.strip().lower()).one_or_none()
    else:
        raise HTTPException(400, "worker_id or employee_code required")
    if worker is None:
        raise HTTPException(404, "Worker not found")
    gate = db.get(Gate, payload.gate_id)
    if gate is None:
        raise HTTPException(404, "Gate not found")

    if payload.entry_time:
        if isinstance(payload.entry_time, str):
            clean_str = payload.entry_time.replace("Z", "")
            try:
                now = datetime.fromisoformat(clean_str)
            except Exception:
                now = datetime.now()
        else:
            now = payload.entry_time
    else:
        now = datetime.now()

    existing = (
        db.query(AttendanceLog)
        .filter(AttendanceLog.worker_id == worker.worker_id, AttendanceLog.exit_time.is_(None))
        .order_by(AttendanceLog.entry_time.desc())
        .first()
    )
    if existing:
        existing.gate_id = payload.gate_id
        existing.status = "PRESENT"
        if payload.entry_time:
            existing.entry_time = now
        create_audit_log(
            db,
            category="ATTENDANCE",
            action="ATTENDANCE_ALREADY_INSIDE",
            status="PRESENT",
            message="Check-in skipped | worker already has open attendance record",
            worker_id=existing.worker_id,
            gate_id=existing.gate_id,
            metadata={"attendance_id": existing.attendance_id, "status": "PRESENT"},
        )
        db.commit()
        db.refresh(existing)
        return _attendance_row(existing, db)

    log = AttendanceLog(
        worker_id=worker.worker_id,
        gate_id=gate.gate_id,
        entry_time=now,
        status="PRESENT",
    )
    db.add(log)
    create_audit_log(
        db,
        category="ATTENDANCE",
        action="ATTENDANCE_CHECKIN",
        status="PRESENT",
        message="Manual check-in | attendance record created",
        worker_id=worker.worker_id,
        gate_id=gate.gate_id,
        metadata={"entry_status": "PRESENT"},
    )
    db.commit()
    db.refresh(log)
    return _attendance_row(log, db)


@router.post("/attendance/{attendance_id}/checkout")
def check_out_worker(
    attendance_id: int,
    db: Session = Depends(get_db),
):
    logger.info(
        "Worker checkout requested | attendance_id=%s",
        attendance_id,
    )

    log = db.get(
        AttendanceLog,
        attendance_id,
    )

    if log is None:
        logger.warning(
            "Checkout failed | attendance_id=%s record_not_found",
            attendance_id,
        )

        raise HTTPException(
            404,
            "Attendance record not found",
        )

    logger.info(
        "Worker checkout started | "
        "attendance_id=%s worker_id=%s gate_id=%s "
        "current_status=%s entry_time=%s",
        attendance_id,
        log.worker_id,
        log.gate_id,
        log.status,
        log.entry_time,
    )

    log.exit_time = datetime.now()
    log.status = "OUTSIDE"

    create_audit_log(
        db,
        category="ATTENDANCE",
        action="WORKER_CHECKOUT",
        status="OUTSIDE",
        message=(
            f"Worker checked out | "
            f"attendance_id={log.attendance_id} "
            f"worker_id={log.worker_id}"
        ),
        worker_id=log.worker_id,
        gate_id=log.gate_id,
        metadata={
            "attendance_id": log.attendance_id,
            "exit_status": "OUTSIDE",
        },
    )

    db.commit()
    db.refresh(log)

    logger.info(
        "Worker checkout completed | "
        "attendance_id=%s worker_id=%s gate_id=%s "
        "exit_time=%s status=%s",
        log.attendance_id,
        log.worker_id,
        log.gate_id,
        log.exit_time,
        log.status,
    )

    return _attendance_row(
        log,
        db,
    )



@router.post("/attendance", status_code=status.HTTP_201_CREATED)
def create_attendance(
    payload: AttendanceLogCreate,
    db: Session = Depends(get_db),
):
    logger.info(
        "Attendance creation requested | "
        "event_id=%s worker_id=%s gate_id=%s "
        "entry_time=%s status=%s",
        payload.event_id,
        payload.worker_id,
        payload.gate_id,
        payload.entry_time,
        payload.status,
    )

    log = AttendanceLog(
        **payload.model_dump()
    )

    db.add(log)

    create_audit_log(
        db,
        category="ATTENDANCE",
        action="ATTENDANCE_CREATED",
        status=payload.status,
        message=(
            f"Attendance created via API | "
            f"worker_id={payload.worker_id} "
            f"gate_id={payload.gate_id} "
            f"status={payload.status}"
        ),
        event_id=payload.event_id,
        worker_id=payload.worker_id,
        gate_id=payload.gate_id,
        metadata={
            "status": payload.status,
            "entry_time": str(payload.entry_time),
        },
    )

    db.commit()

    db.refresh(log)

    logger.info(
        "Attendance created | "
        "attendance_id=%s event_id=%s worker_id=%s "
        "gate_id=%s entry_time=%s status=%s",
        log.attendance_id,
        log.event_id,
        log.worker_id,
        log.gate_id,
        log.entry_time,
        log.status,
    )

    return _attendance_row(
        log,
        db,
    )



@router.get("/attendance/{attendance_id}")
def get_attendance(attendance_id: int, db: Session = Depends(get_db)):
    log = db.get(AttendanceLog, attendance_id)
    if log is None:
        raise HTTPException(404, "Attendance record not found")
    return _attendance_row(log, db)


@router.patch("/attendance/{attendance_id}")
def update_attendance(attendance_id: int, payload: AttendanceLogUpdate, db: Session = Depends(get_db)):
    log = db.get(AttendanceLog, attendance_id)
    if log is None:
        raise HTTPException(404, "Attendance record not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(log, field, value)
    db.commit()
    db.refresh(log)
    return _attendance_row(log, db)


@router.delete("/attendance/{attendance_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attendance(attendance_id: int, db: Session = Depends(get_db)):
    log = db.get(AttendanceLog, attendance_id)
    if log is None:
        raise HTTPException(404, "Attendance record not found")
    db.delete(log)
    db.commit()
    return Response(status_code=204)


@router.get("/alerts")
def list_alerts(date: str | None = None, shift: str | None = None, gate_id: int | None = None, worker: str | None = None, db: Session = Depends(get_db)):
    selected, shift, gate_id = _query_filters(date, shift, gate_id)
    query = db.query(Alert).outerjoin(ComplianceLog, Alert.log_id == ComplianceLog.log_id)
    if selected: query = query.filter(func.date(Alert.created_at) == selected)
    if gate_id: query = query.filter((Alert.gate_id == gate_id) | (ComplianceLog.gate_id == gate_id))
    if shift or worker:
        query = query.join(Worker, Worker.worker_id == Alert.worker_id)
        # Shift is retained in the public filter contract but workers no longer store a shift designation.
        if worker: query = query.filter((Worker.name.ilike(f"%{worker}%")) | (Worker.employee_code.ilike(f"%{worker}%")))
    return [_alert_row(alert) for alert in query.order_by(Alert.created_at.desc()).all()]


@router.post("/alerts", status_code=status.HTTP_201_CREATED)
def create_alert(payload: AlertCreate, db: Session = Depends(get_db)):
    alert = Alert(**payload.model_dump())
    db.add(alert)
    create_audit_log(
        db,
        category="ALERT",
        action="ALERT_CREATED",
        status=payload.severity,
        message=(
            f"Alert created via API | "
            f"type={payload.alert_type} "
            f"severity={payload.severity}"
        ),
        event_id=payload.event_id,
        worker_id=payload.worker_id,
        gate_id=payload.gate_id,
        metadata={
            "alert_type": payload.alert_type,
            "severity": payload.severity,
        },
    )
    db.commit()
    db.refresh(alert)
    return _alert_row(alert)


@router.get("/alerts/{alert_id}")
def get_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(404, "Alert not found")
    return _alert_row(alert)


@router.patch("/alerts/{alert_id}")
def update_alert(alert_id: int, payload: AlertUpdate, db: Session = Depends(get_db)):
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(404, "Alert not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(alert, field, value)
    db.commit()
    db.refresh(alert)
    return _alert_row(alert)


@router.delete("/alerts/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_alert(alert_id: int, db: Session = Depends(get_db)):
    alert = db.get(Alert, alert_id)
    if alert is None:
        raise HTTPException(404, "Alert not found")
    db.delete(alert)
    db.commit()
    return Response(status_code=204)


@router.get("/compliance")
def list_compliance(limit: int = Query(500, ge=1, le=5000), sync_status: str | None = None, worker_id: int | None = None, db: Session = Depends(get_db)):
    query = db.query(ComplianceLog)
    if sync_status:
        query = query.filter(ComplianceLog.sync_status == sync_status.upper())
    if worker_id:
        query = query.filter(ComplianceLog.worker_id == worker_id)
    logs = query.order_by(ComplianceLog.entry_time.desc()).limit(limit).all()
    return [_compliance_row(log, db) for log in logs]


@router.post("/compliance", status_code=status.HTTP_201_CREATED)
def create_compliance(
    payload: ComplianceLogCreate,
    db: Session = Depends(get_db),
):
    logger.info(
        "Compliance creation requested | "
        "event_id=%s worker_id=%s gate_id=%s "
        "final_verdict=%s overall_status=%s "
        "compliance_score=%s confidence_score=%s",
        payload.event_id,
        payload.worker_id,
        payload.gate_id,
        payload.final_verdict,
        payload.overall_status,
        payload.compliance_score,
        payload.confidence_score,
    )

    log = ComplianceLog(
        **payload.model_dump()
    )

    db.add(log)

    create_audit_log(
        db,
        category="COMPLIANCE",
        action="COMPLIANCE_CREATED",
        status=payload.overall_status,
        message=(
            f"Compliance log created via API | "
            f"verdict={payload.final_verdict} "
            f"status={payload.overall_status}"
        ),
        event_id=payload.event_id,
        worker_id=payload.worker_id,
        gate_id=payload.gate_id,
        metadata={
            "final_verdict": payload.final_verdict,
            "overall_status": payload.overall_status,
            "compliance_score": payload.compliance_score,
            "confidence_score": payload.confidence_score,
        },
    )

    db.commit()

    db.refresh(log)

    logger.info(
        "Compliance created | "
        "log_id=%s event_id=%s worker_id=%s gate_id=%s "
        "final_verdict=%s overall_status=%s "
        "compliance_score=%s confidence_score=%s",
        log.log_id,
        log.event_id,
        log.worker_id,
        log.gate_id,
        log.final_verdict,
        log.overall_status,
        log.compliance_score,
        log.confidence_score,
    )

    return _compliance_row(
        log,
        db,
    )



@router.get("/compliance/{log_id}")
def get_compliance(log_id: int, db: Session = Depends(get_db)):
    log = db.get(ComplianceLog, log_id)
    if log is None:
        raise HTTPException(404, "Compliance log not found")
    return _compliance_row(log, db)


@router.patch("/compliance/{log_id}")
def update_compliance(log_id: int, payload: ComplianceLogUpdate, db: Session = Depends(get_db)):
    log = db.get(ComplianceLog, log_id)
    if log is None:
        raise HTTPException(404, "Compliance log not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(log, field, value)
    db.commit()
    db.refresh(log)
    return _compliance_row(log, db)


@router.delete("/compliance/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_compliance(log_id: int, db: Session = Depends(get_db)):
    log = db.get(ComplianceLog, log_id)
    if log is None:
        raise HTTPException(404, "Compliance log not found")
    db.delete(log)
    db.commit()
    return Response(status_code=204)


@router.get("/reports")
def list_reports(date: str | None = None, shift: str | None = None, gate_id: int | None = None, worker: str | None = None, db: Session = Depends(get_db)):
    selected, shift, gate_id = _query_filters(date, shift, gate_id)
    query = db.query(Report)
    if selected:
        query = query.filter(Report.period_start <= selected, Report.period_end >= selected)
    if worker:
        worker_obj = db.query(Worker).filter(
            or_(Worker.employee_code.ilike(f"%{worker}%"), Worker.name.ilike(f"%{worker}%"))
        ).first()
        if worker_obj:
            query = query.filter(Report.generated_by == worker_obj.worker_id)
    reports = [_report_row(report, db) for report in query.order_by(Report.generated_at.desc()).all()]
    return reports


@router.post("/reports", status_code=status.HTTP_201_CREATED)
def create_report(payload: ReportCreate, db: Session = Depends(get_db)):
    report = Report(**payload.model_dump())
    db.add(report)
    db.commit()
    db.refresh(report)
    return _report_row(report, db)


@router.get("/reports/{report_id}")
def get_report(report_id: int, db: Session = Depends(get_db)):
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(404, "Report not found")
    return _report_row(report, db)


@router.get("/reports/{report_id}/download")
def download_report_by_id(report_id: int, db: Session = Depends(get_db)):
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(404, "Report not found")

    period_type = "MONTHLY" if "MONTHLY" in (report.report_type or "").upper() else "WEEKLY"
    if report.generated_by:
        worker = db.get(Worker, report.generated_by)
        if not worker:
            raise HTTPException(404, "Worker associated with report not found")
        try:
            pdf_bytes = generate_employee_report(
                db=db,
                worker_id=worker.worker_id,
                start_date=report.period_start,
                end_date=report.period_end,
                period_type=period_type,
            )
        except Exception as exc:
            logger.error("Employee PDF download failed | error=%s", exc, exc_info=True)
            raise HTTPException(500, "Failed to generate report PDF") from exc
        filename = report.file_url or f"SURAKSHA_Employee_{period_type}_{worker.employee_code}_{report.period_end}.pdf"
    else:
        try:
            pdf_bytes = generate_all_employees_report(
                db=db,
                start_date=report.period_start,
                end_date=report.period_end,
                period_type=period_type,
            )
        except Exception as exc:
            logger.error("All-Employees PDF download failed | error=%s", exc, exc_info=True)
            raise HTTPException(500, "Failed to generate workforce report PDF") from exc
        filename = report.file_url or f"SURAKSHA_All_Employees_{period_type}_{report.period_end}.pdf"

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.patch("/reports/{report_id}")
def update_report(report_id: int, payload: ReportUpdate, db: Session = Depends(get_db)):
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(404, "Report not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(report, field, value)
    db.commit()
    db.refresh(report)
    return _report_row(report, db)


@router.delete("/reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_report(report_id: int, db: Session = Depends(get_db)):
    report = db.get(Report, report_id)
    if report is None:
        raise HTTPException(404, "Report not found")
    db.delete(report)
    db.commit()
    return Response(status_code=204)


def _resolve_report_dates(period: str | None, date_str: str | None, month_str: str | None) -> tuple[date_type, date_type, str]:
    normalized_period = (period or "WEEKLY").upper()
    if normalized_period not in ("WEEKLY", "MONTHLY"):
        raise HTTPException(status_code=400, detail="Period must be WEEKLY or MONTHLY")

    if normalized_period == "MONTHLY":
        if month_str:
            try:
                parts = month_str.strip().split("-")
                parsed_year, parsed_month = int(parts[0]), int(parts[1])
                start_date = date_type(parsed_year, parsed_month, 1)
                num_days = calendar.monthrange(parsed_year, parsed_month)[1]
                end_date = date_type(parsed_year, parsed_month, num_days)
            except Exception:
                raise HTTPException(status_code=400, detail="month must be formatted as YYYY-MM")
        elif date_str:
            try:
                dt = datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
                start_date = date_type(dt.year, dt.month, 1)
                num_days = calendar.monthrange(dt.year, dt.month)[1]
                end_date = date_type(dt.year, dt.month, num_days)
            except Exception:
                raise HTTPException(status_code=400, detail="date must be formatted as YYYY-MM-DD")
        else:
            today = datetime.now(timezone.utc).date()
            start_date = date_type(today.year, today.month, 1)
            num_days = calendar.monthrange(today.year, today.month)[1]
            end_date = date_type(today.year, today.month, num_days)
    else:  # WEEKLY
        if date_str:
            try:
                ref_date = datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
            except Exception:
                raise HTTPException(status_code=400, detail="date must be formatted as YYYY-MM-DD")
        else:
            ref_date = datetime.now(timezone.utc).date()
        # 7-day reporting period ending on reference date
        start_date = ref_date - timedelta(days=6)
        end_date = ref_date

    return start_date, end_date, normalized_period


def _resolve_worker_entity(worker_id_val: str | int, db: Session) -> Worker:
    val_str = str(worker_id_val).strip()
    worker = None
    if val_str.isdigit():
        worker = db.get(Worker, int(val_str))
    if worker is None:
        worker = db.query(Worker).filter(func.lower(Worker.employee_code) == val_str.lower()).one_or_none()
    if worker is None:
        raise HTTPException(status_code=404, detail=f"Worker '{worker_id_val}' not found")
    return worker


@router.get("/reports/pdf/employee/{worker_id}")
def download_employee_report_pdf(
    worker_id: str,
    period: str = Query("WEEKLY", description="WEEKLY or MONTHLY"),
    date: str | None = Query(None, description="Reference date YYYY-MM-DD"),
    month: str | None = Query(None, description="Month YYYY-MM for monthly report"),
    shift: str | None = Query(None, description="Shift filter (A, B, C or ALL)"),
    gate_id: int | None = Query(None, description="Checkpoint gate ID"),
    db: Session = Depends(get_db),
):
    worker = _resolve_worker_entity(worker_id, db)
    start_date, end_date, normalized_period = _resolve_report_dates(period, date, month)
    shift_val = shift.upper() if shift and shift.upper() != "ALL" else None

    try:
        pdf_bytes = generate_employee_report(
            db=db,
            worker_id=worker.worker_id,
            start_date=start_date,
            end_date=end_date,
            period_type=normalized_period,
            shift=shift_val,
            gate_id=gate_id,
        )
    except Exception as exc:
        logger.error("Employee PDF generation failed | worker_id=%s error=%s", worker.worker_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate employee safety report PDF") from exc

    if normalized_period == "MONTHLY":
        filename = f"SURAKSHA_Employee_Monthly_{worker.employee_code}_{start_date.strftime('%Y-%m')}.pdf"
        rpt_type = "MONTHLY"
    else:
        filename = f"SURAKSHA_Employee_Weekly_{worker.employee_code}_{end_date.strftime('%Y-%m-%d')}.pdf"
        rpt_type = "WEEKLY"

    # Audit logging
    create_audit_log(
        db,
        category="REPORT",
        action="REPORT_GENERATED",
        status="GENERATED",
        message=f"{normalized_period.title()} safety report generated for employee {worker.name} ({worker.employee_code})",
        worker_id=worker.worker_id,
        gate_id=gate_id,
        metadata={
            "scope": "INDIVIDUAL_EMPLOYEE",
            "report_type": rpt_type,
            "period": normalized_period,
            "worker_id": worker.worker_id,
            "employee_code": worker.employee_code,
            "start_date": str(start_date),
            "end_date": str(end_date),
            "shift": shift_val,
            "gate_id": gate_id,
            "filename": filename,
        },
    )

    # Save to Report table
    report_record = Report(
        report_type=rpt_type,
        period_start=start_date,
        period_end=end_date,
        generated_by=worker.worker_id,
        file_url=filename,
    )
    db.add(report_record)
    db.commit()

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.get("/reports/pdf/all")
def download_all_employees_report_pdf(
    period: str = Query("WEEKLY", description="WEEKLY or MONTHLY"),
    date: str | None = Query(None, description="Reference date YYYY-MM-DD"),
    month: str | None = Query(None, description="Month YYYY-MM for monthly report"),
    shift: str | None = Query(None, description="Shift filter (A, B, C or ALL)"),
    gate_id: int | None = Query(None, description="Checkpoint gate ID"),
    db: Session = Depends(get_db),
):
    start_date, end_date, normalized_period = _resolve_report_dates(period, date, month)
    shift_val = shift.upper() if shift and shift.upper() != "ALL" else None

    try:
        pdf_bytes = generate_all_employees_report(
            db=db,
            start_date=start_date,
            end_date=end_date,
            period_type=normalized_period,
            shift=shift_val,
            gate_id=gate_id,
        )
    except Exception as exc:
        logger.error("All-Employees PDF generation failed | error=%s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail="Failed to generate workforce safety report PDF") from exc

    if normalized_period == "MONTHLY":
        filename = f"SURAKSHA_All_Employees_Monthly_{start_date.strftime('%Y-%m')}.pdf"
        rpt_type = "MONTHLY"
    else:
        filename = f"SURAKSHA_All_Employees_Weekly_{end_date.strftime('%Y-%m-%d')}.pdf"
        rpt_type = "WEEKLY"

    create_audit_log(
        db,
        category="REPORT",
        action="REPORT_GENERATED",
        status="GENERATED",
        message=f"{normalized_period.title()} workforce safety report generated for mine",
        gate_id=gate_id,
        metadata={
            "scope": "ALL_EMPLOYEES",
            "report_type": rpt_type,
            "period": normalized_period,
            "start_date": str(start_date),
            "end_date": str(end_date),
            "shift": shift_val,
            "gate_id": gate_id,
            "filename": filename,
        },
    )

    report_record = Report(
        report_type=rpt_type,
        period_start=start_date,
        period_end=end_date,
        file_url=filename,
    )
    db.add(report_record)
    db.commit()

    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.get("/reports/weekly/employee/{worker_id}")
def get_weekly_employee_report_pdf(worker_id: str, date: str | None = None, shift: str | None = None, gate_id: int | None = None, db: Session = Depends(get_db)):
    return download_employee_report_pdf(worker_id=worker_id, period="WEEKLY", date=date, shift=shift, gate_id=gate_id, db=db)


@router.get("/reports/monthly/employee/{worker_id}")
def get_monthly_employee_report_pdf(worker_id: str, month: str | None = None, date: str | None = None, shift: str | None = None, gate_id: int | None = None, db: Session = Depends(get_db)):
    return download_employee_report_pdf(worker_id=worker_id, period="MONTHLY", date=date, month=month, shift=shift, gate_id=gate_id, db=db)


@router.get("/reports/weekly/all")
def get_weekly_all_employees_report_pdf(date: str | None = None, shift: str | None = None, gate_id: int | None = None, db: Session = Depends(get_db)):
    return download_all_employees_report_pdf(period="WEEKLY", date=date, shift=shift, gate_id=gate_id, db=db)


@router.get("/reports/monthly/all")
def get_monthly_all_employees_report_pdf(month: str | None = None, date: str | None = None, shift: str | None = None, gate_id: int | None = None, db: Session = Depends(get_db)):
    return download_all_employees_report_pdf(period="MONTHLY", date=date, month=month, shift=shift, gate_id=gate_id, db=db)


@router.get("/audit")
def list_audit(limit: int = Query(500, ge=1, le=5000), db: Session = Depends(get_db)):
    events = db.query(GateEvent).filter(GateEvent.lifecycle == "FINALIZED").order_by(GateEvent.edge_timestamp.desc()).limit(limit).all()
    legacy = db.query(ComplianceLog).filter(ComplianceLog.event_id.is_(None)).order_by(ComplianceLog.entry_time.desc()).limit(limit).all()
    rows = [_gate_event_row(event) for event in events] + [_compliance_row(log, db) for log in legacy]
    return sorted(rows, key=lambda row: row.get("time") or "", reverse=True)[:limit]


@router.get("/champions")
def list_champions(db: Session = Depends(get_db)):
    scores = db.query(SafetyScore).join(Worker).order_by(SafetyScore.compliance_rate.desc()).all()
    return [
        {"rank": index, "worker": score.worker.name, "workerId": score.worker.employee_code, "compliance": score.compliance_rate, "streak": 0}
        for index, score in enumerate(scores, start=1)
    ]


@router.get("/insights")
def insights(date: str | None = None, shift: str | None = None, gate_id: int | None = None, worker: str | None = None, db: Session = Depends(get_db)):
    selected, shift, gate_id = _query_filters(date, shift, gate_id)
    shift_query = db.query(func.avg(ComplianceLog.compliance_score), func.count(ComplianceLog.log_id)).join(ComplianceLog, ComplianceLog.worker_id == Worker.worker_id)
    if selected: shift_query = shift_query.filter(func.date(ComplianceLog.entry_time) == selected)
    if gate_id: shift_query = shift_query.filter(ComplianceLog.gate_id == gate_id)
    if worker: shift_query = shift_query.filter((Worker.name.ilike(f"%{worker}%")) | (Worker.employee_code.ilike(f"%{worker}%")))
    shift_rows = shift_query.all()
    risk_query = db.query(Worker, SafetyScore).join(SafetyScore, SafetyScore.worker_id == Worker.worker_id)
    if worker: risk_query = risk_query.filter((Worker.name.ilike(f"%{worker}%")) | (Worker.employee_code.ilike(f"%{worker}%")))
    high_risk = risk_query.filter(SafetyScore.risk_level == "HIGH").order_by(SafetyScore.violation_count.desc()).all()
    return {
        "shiftComparison": [{"shift": "All", "compliance": round(float(avg), 1), "violations": 0} for avg, _ in shift_rows if avg is not None],
        "gateViolations": gate_violations(db),
        "highRiskWorkers": [{"id": worker.employee_code, "name": worker.name, "department": worker.department.name, "violations": score.violation_count} for worker, score in high_risk],
        "mostCommonViolations": common_ppe_violations(date, shift, gate_id, worker, db),
    }


@router.get("/dashboard")
def dashboard(date: str | None = None, shift: str | None = None, gate_id: int | None = None, db: Session = Depends(get_db)):
    selected, shift, gate_id = _query_filters(date, shift, gate_id)
    attendance_query = _date_filters(db.query(AttendanceLog), AttendanceLog, selected, shift, gate_id)
    workers_underground = attendance_query.filter(AttendanceLog.status.in_(["PRESENT", "INSIDE"])).with_entities(func.count(func.distinct(AttendanceLog.worker_id))).scalar() or 0
    todays_entries = attendance_query.with_entities(func.count(AttendanceLog.attendance_id)).scalar() or 0
    compliance_query = _date_filters(db.query(ComplianceLog), ComplianceLog, selected, shift, gate_id)
    violations = compliance_query.filter(ComplianceLog.overall_status == "DENIED").with_entities(func.count(ComplianceLog.log_id)).scalar() or 0
    denied = compliance_query.filter(ComplianceLog.overall_status == "DENIED").with_entities(func.count(ComplianceLog.log_id)).scalar() or 0
    latest_scores = db.query(SafetyScore).order_by(SafetyScore.calculated_at.desc()).all()
    compliance = round(sum(s.compliance_rate for s in latest_scores) / len(latest_scores), 1) if latest_scores else None
    return {
        "kpi": {
            "workersUnderground": workers_underground,
            "todaysEntries": todays_entries,
            "ppeCompliance": compliance,
            "violations": violations,
            "entryDenied": denied,
            "highRiskWorkers": sum(s.risk_level == "HIGH" for s in latest_scores),
        },
        "gates": list_gates(db),
        "ppeTrend": ppe_trend(date=date, shift=shift, gate_id=gate_id, db=db),
        "recentEvents": ([_gate_event_row(event) for event in db.query(GateEvent).filter(GateEvent.lifecycle == "FINALIZED").order_by(GateEvent.edge_timestamp.desc()).limit(5).all()] or [_compliance_row(log, db) for log in db.query(ComplianceLog).order_by(ComplianceLog.entry_time.desc()).limit(5).all()]),
    }
