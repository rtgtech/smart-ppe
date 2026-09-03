import asyncio

from fastapi import APIRouter, Depends, HTTPException, Path, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Alert, AttendanceLog, ComplianceLog, Report, SafetyScore, WorkerPpe
from app.schemas.department import DepartmentRead
from app.schemas.worker import WorkerCreate, WorkerUpdate
from app.services import workers as worker_service
from app.services.face_recognition import FaceServiceError
from app.services.vision import require_face_services

router = APIRouter(prefix="/workers", tags=["workers"])


class WorkerRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    worker_id: int
    id: str
    employee_code: str
    name: str
    department_id: int
    department: str
    designation: str | None
    shift: str
    phone: str | None
    email: str | None
    rfid_uid: str | None
    rfidId: str
    ppeScore: float
    risk: str
    status: str
    violations: int
    denials: int = 0
    streak: int = 0


class WorkerDeleteResponse(BaseModel):
    worker_id: int
    status: str
    message: str


def to_worker_row(db: Session, worker) -> WorkerRow:
    score = worker_service.latest_safety_score(db, worker.worker_id)
    ppe_score = score.compliance_rate if score else 100
    risk = score.risk_level if score else "LOW"
    violations = score.violation_count if score else 0
    designation = worker.designation or ""
    shift = designation.replace("Shift", "").strip() or "A"

    return WorkerRow(
        worker_id=worker.worker_id,
        id=worker.employee_code,
        employee_code=worker.employee_code,
        name=worker.name,
        department_id=worker.department_id,
        department=worker.department.name if worker.department else "",
        designation=worker.designation,
        shift=shift,
        phone=worker.phone,
        email=worker.email,
        rfid_uid=worker.rfid_uid,
        rfidId=worker.rfid_uid or "",
        ppeScore=ppe_score,
        risk=risk,
        status=worker.status,
        violations=violations,
    )


def ensure_unique_worker_fields(db: Session, payload: WorkerCreate | WorkerUpdate, current_worker_id: int | None = None) -> None:
    data = payload.model_dump(exclude_unset=True)

    employee_code = data.get("employee_code")
    if employee_code:
        existing = worker_service.get_worker_by_code(db, employee_code)
        if existing and existing.worker_id != current_worker_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Employee code already exists")

    rfid_uid = data.get("rfid_uid")
    if rfid_uid:
        existing = worker_service.get_worker_by_rfid(db, rfid_uid)
        if existing and existing.worker_id != current_worker_id:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="RFID UID already exists")


@router.get("/departments", response_model=list[DepartmentRead])
def get_departments(db: Session = Depends(get_db)):
    return worker_service.list_departments(db)


@router.get("", response_model=list[WorkerRow])
def get_workers(db: Session = Depends(get_db)):
    return [to_worker_row(db, worker) for worker in worker_service.list_workers(db)]


@router.get("/by-code/{employee_code}", response_model=WorkerRow)
def get_worker_by_employee_code(employee_code: str, db: Session = Depends(get_db)):
    worker = worker_service.get_worker_by_code(db, employee_code)
    if worker is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found")
    return to_worker_row(db, worker)


@router.get("/{worker_id}", response_model=WorkerRow)
def get_worker(worker_id: int = Path(gt=0), db: Session = Depends(get_db)):
    worker = worker_service.get_worker(db, worker_id)
    if worker is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found")
    return to_worker_row(db, worker)


@router.post("", response_model=WorkerRow, status_code=status.HTTP_201_CREATED)
def create_worker(payload: WorkerCreate, db: Session = Depends(get_db)):
    ensure_unique_worker_fields(db, payload)
    worker = worker_service.create_worker(db, payload)
    return to_worker_row(db, worker)


@router.patch("/{worker_id}", response_model=WorkerRow)
def update_worker(worker_id: int, payload: WorkerUpdate, db: Session = Depends(get_db)):
    worker = worker_service.get_worker(db, worker_id)
    if worker is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found")
    ensure_unique_worker_fields(db, payload, current_worker_id=worker_id)
    worker = worker_service.update_worker(db, worker, payload)
    return to_worker_row(db, worker)


@router.delete("/{worker_id}", response_model=WorkerDeleteResponse)
async def delete_worker(worker_id: int, db: Session = Depends(get_db)):
    worker = worker_service.get_worker(db, worker_id)
    if worker is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found")

    _, registry = require_face_services()
    employee_code = worker.employee_code
    try:
        face_backup = await asyncio.to_thread(registry.profile_snapshot, employee_code)
    except FaceServiceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    face_deleted = False
    try:
        db.query(Alert).filter(Alert.worker_id == worker_id).delete(synchronize_session=False)
        db.query(AttendanceLog).filter(AttendanceLog.worker_id == worker_id).delete(synchronize_session=False)
        db.query(ComplianceLog).filter(ComplianceLog.worker_id == worker_id).delete(synchronize_session=False)
        db.query(WorkerPpe).filter(WorkerPpe.worker_id == worker_id).delete(synchronize_session=False)
        db.query(SafetyScore).filter(SafetyScore.worker_id == worker_id).delete(synchronize_session=False)
        db.query(Report).filter(Report.generated_by == worker_id).update(
            {Report.generated_by: None}, synchronize_session=False
        )
        db.delete(worker)
        db.flush()

        if face_backup is not None:
            face_deleted = await asyncio.to_thread(registry.delete, employee_code)
        db.commit()
    except Exception as exc:
        db.rollback()
        if face_deleted and face_backup is not None:
            try:
                await asyncio.to_thread(registry.restore_snapshot, face_backup)
            except FaceServiceError as restore_error:
                raise HTTPException(
                    status_code=500,
                    detail="Worker deletion failed and the face profile could not be restored.",
                ) from restore_error
        if isinstance(exc, HTTPException):
            raise
        raise HTTPException(status_code=500, detail="Worker could not be permanently deleted.") from exc

    return WorkerDeleteResponse(
        worker_id=worker_id,
        status="DELETED",
        message="Worker details, history, and face profile permanently deleted",
    )
