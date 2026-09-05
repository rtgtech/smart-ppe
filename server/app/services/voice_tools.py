import json
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, selectinload

from app.db.session import SessionLocal
from app.models import ComplianceLog, GateEvent, PpeDetection, PpeItem, Worker

LIST_WORKER_NAMES_TOOL = "list_worker_names"
LIST_RECENT_WORKERS_TOOL = "list_recent_workers"
TODAY_PPE_VIOLATIONS_TOOL = "get_today_ppe_violations"
GET_VIOLATIONS_TOOL = "get_violations"
INDIA_TIMEZONE = timezone(timedelta(hours=5, minutes=30), name="Asia/Kolkata")
PPE_DISPLAY_NAMES = {"Shoes": "Boots"}


def fetch_worker_names(db: Session) -> dict:
    workers = (
        db.query(Worker.name, Worker.employee_code)
        .order_by(Worker.name.asc(), Worker.employee_code.asc())
        .all()
    )
    return {
        "count": len(workers),
        "workers": [
            {"name": name, "employee_code": employee_code}
            for name, employee_code in workers
        ],
    }


def execute_list_worker_names() -> dict:
    with SessionLocal() as db:
        return fetch_worker_names(db)


def _iso_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _iso_india(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(INDIA_TIMEZONE).isoformat()


def fetch_recent_workers(db: Session, now: datetime | None = None) -> dict:
    current_time = now or datetime.now(timezone.utc)
    cutoff = current_time - timedelta(days=1)
    workers = (
        db.query(Worker.name, Worker.employee_code, Worker.created_at)
        .filter(Worker.created_at >= cutoff, Worker.created_at <= current_time)
        .order_by(Worker.created_at.desc(), Worker.name.asc())
        .all()
    )
    return {
        "window_hours": 24,
        "count": len(workers),
        "workers": [
            {
                "name": name,
                "employee_code": employee_code,
                "added_at": _iso_utc(created_at),
            }
            for name, employee_code, created_at in workers
        ],
    }


def execute_list_recent_workers() -> dict:
    with SessionLocal() as db:
        return fetch_recent_workers(db)


def fetch_today_ppe_violations(db: Session, now: datetime | None = None) -> dict:
    current_time = now or datetime.now(INDIA_TIMEZONE)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=INDIA_TIMEZONE)
    local_time = current_time.astimezone(INDIA_TIMEZONE)
    day_start = local_time.replace(hour=0, minute=0, second=0, microsecond=0)
    start_utc = day_start.astimezone(timezone.utc)
    current_utc = local_time.astimezone(timezone.utc)

    filters = (
        ComplianceLog.entry_time >= start_utc,
        ComplianceLog.entry_time <= current_utc,
        ComplianceLog.overall_status == "DENIED",
        ComplianceLog.data_origin != "DEMO",
        PpeDetection.detected.is_(False),
    )
    rows = (
        db.query(PpeItem.name, func.count(PpeDetection.detection_id))
        .join(PpeDetection, PpeDetection.ppe_id == PpeItem.ppe_id)
        .join(ComplianceLog, ComplianceLog.log_id == PpeDetection.log_id)
        .filter(*filters)
        .group_by(PpeItem.name)
        .order_by(func.count(PpeDetection.detection_id).desc(), PpeItem.name.asc())
        .all()
    )
    event_count = (
        db.query(func.count(func.distinct(ComplianceLog.log_id)))
        .join(PpeDetection, PpeDetection.log_id == ComplianceLog.log_id)
        .filter(*filters)
        .scalar()
        or 0
    )
    breakdown = [
        {"ppe_item": PPE_DISPLAY_NAMES.get(name, name), "violations": count}
        for name, count in rows
    ]
    return {
        "date": local_time.date().isoformat(),
        "timezone": "Asia/Kolkata",
        "total_violations": sum(row["violations"] for row in breakdown),
        "violation_events": event_count,
        "by_ppe_item": breakdown,
        "data_scope": "NON_DEMO",
    }


def execute_today_ppe_violations() -> dict:
    with SessionLocal() as db:
        return fetch_today_ppe_violations(db)


def _worker_summary(worker: Worker) -> dict:
    return {
        "name": worker.name,
        "employee_code": worker.employee_code,
        "status": worker.status,
    }


def _resolve_violation_worker(db: Session, value: str) -> dict:
    normalized = value.strip()
    query = db.query(Worker)
    exact_code = query.filter(func.lower(Worker.employee_code) == normalized.lower()).one_or_none()
    if exact_code:
        return {"status": "RESOLVED", "worker": exact_code, "candidates": []}

    exact_names = (
        query.filter(func.lower(Worker.name) == normalized.lower())
        .order_by(Worker.employee_code.asc())
        .limit(6)
        .all()
    )
    if len(exact_names) == 1:
        return {"status": "RESOLVED", "worker": exact_names[0], "candidates": []}
    if len(exact_names) > 1:
        return {
            "status": "AMBIGUOUS_WORKER",
            "worker": None,
            "candidates": [_worker_summary(worker) for worker in exact_names],
        }

    candidates = (
        query.filter(or_(
            func.lower(Worker.name).contains(normalized.lower(), autoescape=True),
            func.lower(Worker.employee_code).contains(normalized.lower(), autoescape=True),
        ))
        .order_by(Worker.name.asc(), Worker.employee_code.asc())
        .limit(6)
        .all()
    )
    if len(candidates) == 1:
        return {"status": "RESOLVED", "worker": candidates[0], "candidates": []}
    return {
        "status": "AMBIGUOUS_WORKER" if candidates else "WORKER_NOT_FOUND",
        "worker": None,
        "candidates": [_worker_summary(worker) for worker in candidates],
    }


def _violation_date_window(
    date_value: str | None,
    now: datetime,
) -> tuple[datetime | None, datetime | None, str]:
    if not date_value or not date_value.strip() or date_value.strip().lower() == "latest":
        return None, None, "latest"

    value = date_value.strip().lower()
    local_now = now.astimezone(INDIA_TIMEZONE)
    if value in {"today", "present day", "current day"}:
        selected = local_now.date()
    elif value == "yesterday":
        selected = local_now.date() - timedelta(days=1)
    else:
        try:
            selected = datetime.strptime(value, "%Y-%m-%d").date()
        except ValueError:
            return None, None, "invalid"

    start_local = datetime.combine(selected, datetime.min.time(), tzinfo=INDIA_TIMEZONE)
    end_local = start_local + timedelta(days=1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc), selected.isoformat()


def _violation_row(log: ComplianceLog, db: Session) -> dict:
    missing = sorted({
        PPE_DISPLAY_NAMES.get(detection.ppe_item.name, detection.ppe_item.name)
        for detection in log.detections
        if not detection.detected and detection.ppe_item is not None
    })
    reasons = []
    if log.event_id:
        event = db.get(GateEvent, log.event_id)
        if event:
            try:
                decoded = json.loads(event.reasons_json)
                reasons = decoded if isinstance(decoded, list) else []
            except (TypeError, json.JSONDecodeError):
                reasons = []
    return {
        "violation_id": log.log_id,
        "event_id": log.event_id,
        "occurred_at": _iso_india(log.entry_time),
        "worker": _worker_summary(log.worker),
        "gate": {
            "name": log.gate.name,
            "location": log.gate.location,
        } if log.gate else None,
        "decision": log.final_verdict or log.overall_status,
        "missing_ppe": missing,
        "reason_codes": reasons,
        "compliance_score": log.compliance_score,
        "data_origin": log.data_origin,
    }


def fetch_violations(
    db: Session,
    worker_name: str | None = None,
    date_value: str | None = None,
    now: datetime | None = None,
) -> dict:
    current_time = now or datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)
    start, end, selected_date = _violation_date_window(date_value, current_time)
    query_context = {
        "worker_name": worker_name.strip() if worker_name and worker_name.strip() else None,
        "date": selected_date,
    }
    if selected_date == "invalid":
        return {
            "status": "INVALID_DATE",
            "query": query_context,
            "message": "Use today, yesterday, latest, or a date in YYYY-MM-DD format.",
            "violation_count": 0,
            "violations": [],
        }

    worker = None
    if query_context["worker_name"]:
        resolution = _resolve_violation_worker(db, query_context["worker_name"])
        if resolution["status"] != "RESOLVED":
            return {
                "status": resolution["status"],
                "query": query_context,
                "candidates": resolution["candidates"],
                "violation_count": 0,
                "violations": [],
            }
        worker = resolution["worker"]

    filters = [
        ComplianceLog.overall_status.in_(("DENIED", "NON_COMPLIANT")),
        ComplianceLog.data_origin != "DEMO",
        ComplianceLog.entry_time <= current_time.astimezone(timezone.utc),
    ]
    if worker is not None:
        filters.append(ComplianceLog.worker_id == worker.worker_id)
    if start is not None and end is not None:
        filters.extend((ComplianceLog.entry_time >= start, ComplianceLog.entry_time < end))

    base_query = db.query(ComplianceLog).filter(*filters)
    violation_count = base_query.count()
    logs = (
        base_query.options(
            selectinload(ComplianceLog.worker),
            selectinload(ComplianceLog.gate),
            selectinload(ComplianceLog.detections).selectinload(PpeDetection.ppe_item),
        )
        .order_by(ComplianceLog.entry_time.desc(), ComplianceLog.log_id.desc())
        .limit(20)
        .all()
    )
    breakdown_rows = (
        db.query(PpeItem.name, func.count(PpeDetection.detection_id))
        .join(PpeDetection, PpeDetection.ppe_id == PpeItem.ppe_id)
        .join(ComplianceLog, ComplianceLog.log_id == PpeDetection.log_id)
        .filter(*filters, PpeDetection.detected.is_(False))
        .group_by(PpeItem.name)
        .order_by(func.count(PpeDetection.detection_id).desc(), PpeItem.name.asc())
        .all()
    )
    return {
        "status": "OK",
        "query": query_context,
        "timezone": "Asia/Kolkata",
        "worker": _worker_summary(worker) if worker else None,
        "violation_count": violation_count,
        "returned_count": len(logs),
        "truncated": violation_count > len(logs),
        "missing_ppe_breakdown": [
            {"ppe_item": PPE_DISPLAY_NAMES.get(name, name), "violations": count}
            for name, count in breakdown_rows
        ],
        "violations": [_violation_row(log, db) for log in logs],
        "data_scope": "NON_DEMO",
    }


def execute_get_violations(
    worker_name: str | None = None,
    date_value: str | None = None,
) -> dict:
    with SessionLocal() as db:
        return fetch_violations(db, worker_name, date_value)
