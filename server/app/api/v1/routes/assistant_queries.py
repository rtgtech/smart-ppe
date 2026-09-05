"""Small, read-only, parameterized API intended for assistant tool wrappers."""

from __future__ import annotations

import json
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from app.db.session import get_db
from app.core.config import get_settings
from app.models import AttendanceLog, ComplianceLog, GateEvent, PpeDetection, Worker


def require_assistant_token(x_assistant_token: str | None = Header(None)) -> None:
    expected = get_settings().assistant_api_token
    if not expected:
        raise HTTPException(503, "Assistant query API is not configured")
    if not x_assistant_token or not secrets.compare_digest(x_assistant_token, expected):
        raise HTTPException(401, "Invalid assistant API token")


router = APIRouter(
    prefix="/assistant",
    tags=["assistant-queries"],
    dependencies=[Depends(require_assistant_token)],
)
VIOLATION_STATUSES = ("DENIED", "NON_COMPLIANT")
PPE_DISPLAY_NAMES = {"Shoes": "Boots"}


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _worker_or_404(db: Session, worker_id: int) -> Worker:
    worker = db.get(Worker, worker_id)
    if worker is None:
        raise HTTPException(404, "Worker not found")
    return worker


def _validate_range(start: datetime | None, end: datetime | None) -> None:
    normalized_start = _query_time(start)
    normalized_end = _query_time(end)
    if normalized_start and normalized_end and normalized_end < normalized_start:
        raise HTTPException(400, "end must be on or after start")
    if normalized_start and normalized_end and normalized_end - normalized_start > timedelta(days=366):
        raise HTTPException(400, "Date range cannot exceed 366 days")


def _query_time(value: datetime | None) -> datetime | None:
    if value is None or value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def _worker_row(worker: Worker) -> dict:
    return {
        "worker_id": worker.worker_id,
        "employee_code": worker.employee_code,
        "name": worker.name,
        "department": worker.department.name if worker.department else None,
        "status": worker.status,
    }


def _violation_row(log: ComplianceLog, db: Session) -> dict:
    missing = [
        PPE_DISPLAY_NAMES.get(row.ppe_item.name, row.ppe_item.name)
        for row in log.detections
        if not row.detected and row.ppe_item is not None
    ]
    reasons: list[str] = []
    if log.event_id:
        event = db.get(GateEvent, log.event_id)
        if event:
            try:
                reasons = json.loads(event.reasons_json)
            except (TypeError, json.JSONDecodeError):
                reasons = []
    return {
        "event_id": log.event_id,
        "log_id": log.log_id,
        "occurred_at": _iso(log.entry_time),
        "worker": _worker_row(log.worker),
        "gate": log.gate.name if log.gate else None,
        "decision": log.final_verdict or log.overall_status,
        "missing_ppe": sorted(set(missing)),
        "reasons": reasons,
        "compliance_score": log.compliance_score,
        "confidence": log.confidence_score,
        "data_origin": log.data_origin,
    }


@router.get("/workers/resolve")
def resolve_worker(
    q: str = Query(min_length=2, max_length=100),
    include_inactive: bool = False,
    db: Session = Depends(get_db),
):
    value = q.strip()
    query = db.query(Worker)
    if not include_inactive:
        query = query.filter(Worker.status == "ACTIVE")

    exact_code = query.filter(func.lower(Worker.employee_code) == value.lower()).one_or_none()
    if exact_code:
        return {"status": "RESOLVED", "worker": _worker_row(exact_code), "candidates": []}

    candidates = (
        query.filter(or_(
            func.lower(Worker.name) == value.lower(),
            Worker.name.ilike(f"%{value}%"),
            Worker.employee_code.ilike(f"%{value}%"),
        ))
        .order_by(Worker.name, Worker.employee_code)
        .limit(6)
        .all()
    )
    rows = [_worker_row(worker) for worker in candidates]
    if len(rows) == 1:
        return {"status": "RESOLVED", "worker": rows[0], "candidates": []}
    return {
        "status": "AMBIGUOUS" if rows else "NOT_FOUND",
        "worker": None,
        "candidates": rows,
    }


@router.get("/workers/{worker_id}/attendance")
def worker_attendance(
    worker_id: int,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = Query(20, ge=1, le=100),
    include_demo: bool = False,
    db: Session = Depends(get_db),
):
    worker = _worker_or_404(db, worker_id)
    _validate_range(start, end)
    start, end = _query_time(start), _query_time(end)
    query = db.query(AttendanceLog).filter(AttendanceLog.worker_id == worker_id)
    if not include_demo:
        query = query.filter(AttendanceLog.data_origin != "DEMO")
    if start:
        query = query.filter(AttendanceLog.entry_time >= start)
    if end:
        query = query.filter(AttendanceLog.entry_time <= end)
    records = query.order_by(AttendanceLog.entry_time.desc()).limit(limit).all()
    return {
        "worker": _worker_row(worker),
        "records": [{
            "attendance_id": row.attendance_id,
            "event_id": row.event_id,
            "entry_time": _iso(row.entry_time),
            "exit_time": _iso(row.exit_time),
            "currently_inside": row.exit_time is None and row.status in {"PRESENT", "INSIDE"},
            "status": row.status,
            "gate": row.gate.name if row.gate else None,
            "data_origin": row.data_origin,
        } for row in records],
    }


def _violation_query(db: Session, include_demo: bool):
    query = (
        db.query(ComplianceLog)
        .options(
            selectinload(ComplianceLog.worker).selectinload(Worker.department),
            selectinload(ComplianceLog.gate),
            selectinload(ComplianceLog.detections).selectinload(PpeDetection.ppe_item),
        )
        .filter(ComplianceLog.overall_status.in_(VIOLATION_STATUSES))
    )
    if not include_demo:
        query = query.filter(ComplianceLog.data_origin != "DEMO")
    return query


@router.get("/workers/{worker_id}/violations")
def worker_violations(
    worker_id: int,
    start: datetime | None = None,
    end: datetime | None = None,
    limit: int = Query(20, ge=1, le=100),
    include_demo: bool = False,
    db: Session = Depends(get_db),
):
    worker = _worker_or_404(db, worker_id)
    _validate_range(start, end)
    start, end = _query_time(start), _query_time(end)
    query = _violation_query(db, include_demo).filter(ComplianceLog.worker_id == worker_id)
    if start:
        query = query.filter(ComplianceLog.entry_time >= start)
    if end:
        query = query.filter(ComplianceLog.entry_time <= end)
    logs = query.order_by(ComplianceLog.entry_time.desc()).limit(limit).all()
    return {"worker": _worker_row(worker), "violations": [_violation_row(log, db) for log in logs]}


@router.get("/violations/latest")
def latest_violations(
    limit: int = Query(10, ge=1, le=100),
    include_demo: bool = False,
    db: Session = Depends(get_db),
):
    logs = _violation_query(db, include_demo).order_by(ComplianceLog.entry_time.desc()).limit(limit).all()
    return {"violations": [_violation_row(log, db) for log in logs]}


@router.get("/workers/{worker_id}/safety-summary")
def worker_safety_summary(
    worker_id: int,
    days: int = Query(30, ge=1, le=366),
    include_demo: bool = False,
    db: Session = Depends(get_db),
):
    worker = _worker_or_404(db, worker_id)
    since = datetime.now(timezone.utc) - timedelta(days=days)
    query = db.query(ComplianceLog).filter(
        ComplianceLog.worker_id == worker_id,
        ComplianceLog.entry_time >= since,
    )
    if not include_demo:
        query = query.filter(ComplianceLog.data_origin != "DEMO")
    logs = query.all()
    if not logs:
        return {"worker": _worker_row(worker), "period_days": days, "score": None, "risk": "UNKNOWN", "events": 0, "violation_events": 0}
    score = round(sum(log.compliance_score for log in logs) / len(logs), 1)
    violations = sum(log.overall_status in VIOLATION_STATUSES for log in logs)
    risk = "LOW" if score >= 90 else "MEDIUM" if score >= 75 else "HIGH"
    return {"worker": _worker_row(worker), "period_days": days, "score": score, "risk": risk, "events": len(logs), "violation_events": violations}
