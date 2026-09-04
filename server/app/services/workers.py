from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Department, SafetyScore, Worker
from app.schemas.worker import WorkerCreate, WorkerUpdate


def list_departments(db: Session) -> list[Department]:
    return db.query(Department).order_by(Department.name.asc()).all()


def list_workers(db: Session) -> list[Worker]:
    return (
        db.query(Worker)
        .join(Department)
        .order_by(Worker.created_at.desc(), Worker.worker_id.desc())
        .all()
    )


def get_worker(db: Session, worker_id: int) -> Worker | None:
    return db.get(Worker, worker_id)


def get_worker_by_code(db: Session, employee_code: str) -> Worker | None:
    return db.query(Worker).filter(func.lower(Worker.employee_code) == employee_code.lower()).one_or_none()


def create_worker(db: Session, payload: WorkerCreate) -> Worker:
    worker = Worker(**payload.model_dump())
    db.add(worker)
    db.commit()
    db.refresh(worker)
    return worker


def update_worker(db: Session, worker: Worker, payload: WorkerUpdate) -> Worker:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(worker, field, value)
    db.commit()
    db.refresh(worker)
    return worker


def deactivate_worker(db: Session, worker: Worker) -> Worker:
    worker.status = "INACTIVE"
    db.commit()
    db.refresh(worker)
    return worker


def latest_safety_score(db: Session, worker_id: int) -> SafetyScore | None:
    return (
        db.query(SafetyScore)
        .filter(SafetyScore.worker_id == worker_id)
        .order_by(SafetyScore.calculated_at.desc(), SafetyScore.score_id.desc())
        .first()
    )
