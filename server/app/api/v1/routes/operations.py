"""REST resources and read models used by the operational frontend."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import (
    Alert,
    AttendanceLog,
    ComplianceLog,
    Department,
    Device,
    Gate,
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


class StatusPatch(BaseModel):
    status: str


def _date_label(value: datetime | None) -> str:
    if value is None:
        return "—"
    return value.astimezone(timezone.utc).strftime("%d %b, %H:%M")


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
        "gate": alert.compliance_log.gate.name if alert.compliance_log and alert.compliance_log.gate else "—",
        "time": _date_label(alert.created_at),
        "status": alert.status,
        "officer": "—",
        "resolved_at": alert.resolved_at,
    }


def _attendance_row(log: AttendanceLog) -> dict:
    return {
        "attendance_id": log.attendance_id,
        "worker": log.worker.name,
        "workerId": log.worker.employee_code,
        "entry": log.entry_time,
        "exit": log.exit_time,
        "ppe": "—",
        "location": log.gate.location,
        "status": log.status,
    }


def _compliance_row(log: ComplianceLog) -> dict:
    return {
        "log_id": log.log_id,
        "id": f"EVT-{log.log_id:05d}",
        "eventId": f"EVT-{log.log_id:05d}",
        "time": log.entry_time,
        "worker": log.worker.name,
        "workerId": log.worker.employee_code,
        "gate": log.gate.name,
        "decision": {"COMPLIANT": "ALLOWED", "NON_COMPLIANT": "WARNING", "DENIED": "DENIED"}.get(log.overall_status, log.overall_status),
        "source": "AI CAMERA",
        "compliance_score": log.compliance_score,
        "confidence_score": log.confidence_score,
        "offline": log.offline_flag,
        "sync_status": log.sync_status,
        "type": "PPE verification",
        "status": log.sync_status.title(),
    }


def _report_row(report: Report, db: Session) -> dict:
    return {
        "report_id": report.report_id,
        "id": f"RPT-{report.report_id:02d}",
        "name": report.report_type.replace("_", " ").title(),
        "description": f"{report.report_type.replace('_', ' ').title()} report",
        "lastGenerated": report.generated_at,
        "records": 0,
        "status": "READY" if report.file_url else "GENERATED",
        "file_url": report.file_url,
        "period_start": report.period_start,
        "period_end": report.period_end,
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
def ppe_summary(db: Session = Depends(get_db)):
    items = db.query(PpeItem).order_by(PpeItem.ppe_id).all()
    rows = []
    for item in items:
        total = db.query(func.count(PpeDetection.detection_id)).filter(PpeDetection.ppe_id == item.ppe_id).scalar() or 0
        detected = db.query(func.count(PpeDetection.detection_id)).filter(PpeDetection.ppe_id == item.ppe_id, PpeDetection.detected.is_(True)).scalar() or 0
        rows.append({
            "key": item.name.lower().replace(" ", ""),
            "label": item.name,
            "compliance": round(detected * 100 / total, 1) if total else None,
            "trend": None,
            "violations": total - detected,
            "is_mandatory": item.is_mandatory,
        })
    return rows


@router.get("/ppe/trend")
def ppe_trend(db: Session = Depends(get_db)):
    since = datetime.now(timezone.utc) - timedelta(days=30)
    rows = db.query(func.date(ComplianceLog.entry_time).label("day"), func.avg(ComplianceLog.compliance_score).label("compliance")).filter(ComplianceLog.entry_time >= since).group_by(func.date(ComplianceLog.entry_time)).order_by("day").all()
    return [{"day": str(row.day), "compliance": round(float(row.compliance), 1)} for row in rows]


@router.get("/ppe/violations")
def common_ppe_violations(db: Session = Depends(get_db)):
    totals = db.query(PpeItem.name, func.count(PpeDetection.detection_id)).join(PpeDetection, PpeDetection.ppe_id == PpeItem.ppe_id).filter(PpeDetection.detected.is_(False)).group_by(PpeItem.name).order_by(func.count(PpeDetection.detection_id).desc()).all()
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


@router.get("/attendance")
def list_attendance(limit: int = Query(500, ge=1, le=5000), db: Session = Depends(get_db)):
    logs = db.query(AttendanceLog).order_by(AttendanceLog.entry_time.desc()).limit(limit).all()
    return [_attendance_row(log) for log in logs]


@router.get("/attendance/kpi")
def attendance_kpi(db: Session = Depends(get_db)):
    today = datetime.now(timezone.utc).date()
    entered = db.query(func.count(AttendanceLog.attendance_id)).filter(func.date(AttendanceLog.entry_time) == today).scalar() or 0
    exited = db.query(func.count(AttendanceLog.attendance_id)).filter(func.date(AttendanceLog.exit_time) == today).scalar() or 0
    underground = db.query(func.count(func.distinct(AttendanceLog.worker_id))).filter(AttendanceLog.status.in_(["PRESENT", "INSIDE"])).scalar() or 0
    missing = db.query(func.count(AttendanceLog.attendance_id)).filter(AttendanceLog.exit_time.is_(None), func.date(AttendanceLog.entry_time) < today).scalar() or 0
    return {"enteredToday": entered, "exitedToday": exited, "currentlyUnderground": underground, "missingExitScans": missing}


@router.get("/attendance/zones")
def attendance_zones(db: Session = Depends(get_db)):
    rows = db.query(Gate.location, func.count(func.distinct(AttendanceLog.worker_id))).join(AttendanceLog, AttendanceLog.gate_id == Gate.gate_id).filter(AttendanceLog.status.in_(["PRESENT", "INSIDE"])).group_by(Gate.location).all()
    return [{"zone": location, "count": count} for location, count in rows]


@router.post("/attendance", status_code=status.HTTP_201_CREATED)
def create_attendance(payload: AttendanceLogCreate, db: Session = Depends(get_db)):
    log = AttendanceLog(**payload.model_dump())
    db.add(log)
    db.commit()
    db.refresh(log)
    return _attendance_row(log)


@router.get("/attendance/{attendance_id}")
def get_attendance(attendance_id: int, db: Session = Depends(get_db)):
    log = db.get(AttendanceLog, attendance_id)
    if log is None:
        raise HTTPException(404, "Attendance record not found")
    return _attendance_row(log)


@router.patch("/attendance/{attendance_id}")
def update_attendance(attendance_id: int, payload: AttendanceLogUpdate, db: Session = Depends(get_db)):
    log = db.get(AttendanceLog, attendance_id)
    if log is None:
        raise HTTPException(404, "Attendance record not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(log, field, value)
    db.commit()
    db.refresh(log)
    return _attendance_row(log)


@router.delete("/attendance/{attendance_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_attendance(attendance_id: int, db: Session = Depends(get_db)):
    log = db.get(AttendanceLog, attendance_id)
    if log is None:
        raise HTTPException(404, "Attendance record not found")
    db.delete(log)
    db.commit()
    return Response(status_code=204)


@router.get("/alerts")
def list_alerts(db: Session = Depends(get_db)):
    return [_alert_row(alert) for alert in db.query(Alert).order_by(Alert.created_at.desc()).all()]


@router.post("/alerts", status_code=status.HTTP_201_CREATED)
def create_alert(payload: AlertCreate, db: Session = Depends(get_db)):
    alert = Alert(**payload.model_dump())
    db.add(alert)
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
    return [_compliance_row(log) for log in logs]


@router.post("/compliance", status_code=status.HTTP_201_CREATED)
def create_compliance(payload: ComplianceLogCreate, db: Session = Depends(get_db)):
    log = ComplianceLog(**payload.model_dump())
    db.add(log)
    db.commit()
    db.refresh(log)
    return _compliance_row(log)


@router.get("/compliance/{log_id}")
def get_compliance(log_id: int, db: Session = Depends(get_db)):
    log = db.get(ComplianceLog, log_id)
    if log is None:
        raise HTTPException(404, "Compliance log not found")
    return _compliance_row(log)


@router.patch("/compliance/{log_id}")
def update_compliance(log_id: int, payload: ComplianceLogUpdate, db: Session = Depends(get_db)):
    log = db.get(ComplianceLog, log_id)
    if log is None:
        raise HTTPException(404, "Compliance log not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(log, field, value)
    db.commit()
    db.refresh(log)
    return _compliance_row(log)


@router.delete("/compliance/{log_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_compliance(log_id: int, db: Session = Depends(get_db)):
    log = db.get(ComplianceLog, log_id)
    if log is None:
        raise HTTPException(404, "Compliance log not found")
    db.delete(log)
    db.commit()
    return Response(status_code=204)


@router.get("/reports")
def list_reports(db: Session = Depends(get_db)):
    return [_report_row(report, db) for report in db.query(Report).order_by(Report.generated_at.desc()).all()]


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


@router.get("/audit")
def list_audit(limit: int = Query(500, ge=1, le=5000), db: Session = Depends(get_db)):
    logs = db.query(ComplianceLog).order_by(ComplianceLog.entry_time.desc()).limit(limit).all()
    return [_compliance_row(log) for log in logs]


@router.get("/champions")
def list_champions(db: Session = Depends(get_db)):
    scores = db.query(SafetyScore).join(Worker).order_by(SafetyScore.compliance_rate.desc()).all()
    return [
        {"rank": index, "worker": score.worker.name, "workerId": score.worker.employee_code, "compliance": score.compliance_rate, "streak": 0}
        for index, score in enumerate(scores, start=1)
    ]


@router.get("/insights")
def insights(db: Session = Depends(get_db)):
    shift_rows = db.query(Worker.designation, func.avg(SafetyScore.compliance_rate), func.count(SafetyScore.score_id)).join(SafetyScore, SafetyScore.worker_id == Worker.worker_id).group_by(Worker.designation).all()
    high_risk = db.query(Worker, SafetyScore).join(SafetyScore, SafetyScore.worker_id == Worker.worker_id).filter(SafetyScore.risk_level == "HIGH").order_by(SafetyScore.violation_count.desc()).all()
    return {
        "shiftComparison": [{"shift": designation or "Unassigned", "compliance": round(float(avg), 1), "violations": 0} for designation, avg, _ in shift_rows],
        "gateViolations": gate_violations(db),
        "highRiskWorkers": [{"id": worker.employee_code, "name": worker.name, "department": worker.department.name, "violations": score.violation_count} for worker, score in high_risk],
        "mostCommonViolations": common_ppe_violations(db),
    }


@router.get("/dashboard")
def dashboard(db: Session = Depends(get_db)):
    workers_underground = (
        db.query(func.count(func.distinct(AttendanceLog.worker_id)))
        .filter(AttendanceLog.status.in_(["PRESENT", "INSIDE"]))
        .scalar()
        or 0
    )
    today = datetime.now(timezone.utc).date()
    todays_entries = db.query(func.count(AttendanceLog.attendance_id)).filter(func.date(AttendanceLog.entry_time) == today).scalar() or 0
    violations = db.query(func.count(ComplianceLog.log_id)).filter(ComplianceLog.overall_status != "COMPLIANT").scalar() or 0
    denied = db.query(func.count(ComplianceLog.log_id)).filter(ComplianceLog.overall_status == "DENIED").scalar() or 0
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
        "ppeTrend": ppe_trend(db),
        "recentEvents": [_compliance_row(log) for log in db.query(ComplianceLog).order_by(ComplianceLog.entry_time.desc()).limit(5).all()],
    }
