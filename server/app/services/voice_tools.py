from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import Worker

LIST_WORKER_NAMES_TOOL = "list_worker_names"
LIST_RECENT_WORKERS_TOOL = "list_recent_workers"


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
