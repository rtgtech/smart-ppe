import asyncio

from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, UploadFile, status
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict, ValidationError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Alert, AttendanceLog, ComplianceLog, Report, SafetyScore, Worker, WorkerPpe
from app.schemas.department import DepartmentRead
from app.schemas.worker import WorkerCreate, WorkerUpdate
from app.services import workers as worker_service
from app.services.face_recognition import FaceServiceError, validate_name, validate_person_id
from app.services.vision import read_registration_images, require_face_registry, require_face_services, vision_lock

router = APIRouter(prefix="/workers", tags=["workers"])


class WorkerRow(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    worker_id: int
    id: str
    employee_code: str
    name: str
    department_id: int
    department: str
    phone: str | None
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

    return WorkerRow(
        worker_id=worker.worker_id,
        id=worker.employee_code,
        employee_code=worker.employee_code,
        name=worker.name,
        department_id=worker.department_id,
        department=worker.department.name if worker.department else "",
        phone=worker.phone,
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


@router.post("/with-face", response_model=WorkerRow, status_code=status.HTTP_201_CREATED)
async def create_worker_with_face(
    worker: str = Form(...),
    images: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    """Create the face profile and worker as one coordinated operation."""
    try:
        payload = WorkerCreate.model_validate_json(worker)
        person_id = validate_person_id(payload.employee_code)
        name = validate_name(payload.name)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=jsonable_encoder(exc.errors())) from exc
    except FaceServiceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    payload = payload.model_copy(update={"employee_code": person_id, "name": name})
    ensure_unique_worker_fields(db, payload)
    engine, registry = require_face_services()
    captures = await read_registration_images(images)

    try:
        async with vision_lock:
            embedding = await asyncio.to_thread(engine.enrollment_embedding, captures)
    except FaceServiceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    face_created = False
    try:
        record = Worker(**payload.model_dump())
        db.add(record)
        db.flush()
        await asyncio.to_thread(registry.create, person_id, name, embedding)
        face_created = True
        response = to_worker_row(db, record)
        db.commit()
        return response
    except FileExistsError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except FaceServiceError as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        db.rollback()
        if face_created:
            try:
                await asyncio.to_thread(registry.delete, person_id)
            except FaceServiceError as cleanup_error:
                raise HTTPException(
                    status_code=500,
                    detail="Worker creation failed and the temporary face profile could not be removed.",
                ) from cleanup_error
        raise HTTPException(status_code=500, detail="Worker and face profile could not be created.") from exc


@router.patch("/{worker_id}", response_model=WorkerRow)
def update_worker(worker_id: int, payload: WorkerUpdate, db: Session = Depends(get_db)):
    worker = worker_service.get_worker(db, worker_id)
    if worker is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found")
    if payload.employee_code is not None and payload.employee_code != worker.employee_code:
        raise HTTPException(status_code=409, detail="Employee code cannot be changed after face enrollment")
    ensure_unique_worker_fields(db, payload, current_worker_id=worker_id)
    worker = worker_service.update_worker(db, worker, payload)
    return to_worker_row(db, worker)


@router.delete("/{worker_id}", response_model=WorkerDeleteResponse)
async def delete_worker(worker_id: int, db: Session = Depends(get_db)):
    worker = worker_service.get_worker(db, worker_id)
    if worker is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Worker not found")

    registry = require_face_registry()
    employee_code = worker.employee_code
    try:
        face_backup = await asyncio.to_thread(registry.profile_snapshot, employee_code)
    except FaceServiceError:
        # Legacy worker IDs may predate face-ID validation and cannot have a
        # matching registry profile. Their database records must remain deletable.
        face_backup = None

    face_deleted = False
    try:
        log_ids = [row[0] for row in db.query(ComplianceLog.log_id).filter(ComplianceLog.worker_id == worker_id).all()]
        alert_filter = Alert.worker_id == worker_id
        if log_ids:
            alert_filter = alert_filter | Alert.log_id.in_(log_ids)
        db.query(Alert).filter(alert_filter).delete(synchronize_session=False)
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
