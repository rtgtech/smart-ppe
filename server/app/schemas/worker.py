from pydantic import BaseModel, EmailStr, Field

from app.schemas.common import OrmModel, WorkerStatus, datetime


class WorkerBase(BaseModel):
    employee_code: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=1, max_length=100)
    photo_url: str | None = None
    department_id: int = Field(gt=0)
    designation: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=15)
    email: EmailStr | None = Field(default=None, max_length=100)
    rfid_uid: str | None = Field(default=None, max_length=50)
    status: WorkerStatus = "ACTIVE"


class WorkerCreate(WorkerBase):
    pass


class WorkerUpdate(BaseModel):
    employee_code: str | None = Field(default=None, min_length=1, max_length=20)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    photo_url: str | None = None
    department_id: int | None = Field(default=None, gt=0)
    designation: str | None = Field(default=None, max_length=100)
    phone: str | None = Field(default=None, max_length=15)
    email: EmailStr | None = Field(default=None, max_length=100)
    rfid_uid: str | None = Field(default=None, max_length=50)
    status: WorkerStatus | None = None


class WorkerRead(WorkerBase, OrmModel):
    worker_id: int
    created_at: datetime
