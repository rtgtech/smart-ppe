from pydantic import BaseModel, Field

from app.schemas.common import OrmModel, WorkerPpeStatus, date, datetime


class WorkerPpeBase(BaseModel):
    worker_id: int = Field(gt=0)
    ppe_id: int = Field(gt=0)
    rfid_tag: str | None = Field(default=None, max_length=50)
    serial_number: str | None = Field(default=None, max_length=50)
    issued_at: datetime | None = None
    expiry_date: date | None = None
    status: WorkerPpeStatus = "ACTIVE"


class WorkerPpeCreate(WorkerPpeBase):
    pass


class WorkerPpeUpdate(BaseModel):
    worker_id: int | None = Field(default=None, gt=0)
    ppe_id: int | None = Field(default=None, gt=0)
    rfid_tag: str | None = Field(default=None, max_length=50)
    serial_number: str | None = Field(default=None, max_length=50)
    issued_at: datetime | None = None
    expiry_date: date | None = None
    status: WorkerPpeStatus | None = None


class WorkerPpeRead(WorkerPpeBase, OrmModel):
    worker_ppe_id: int
    issued_at: datetime
