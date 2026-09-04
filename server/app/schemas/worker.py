from pydantic import BaseModel, Field

from app.schemas.common import OrmModel, WorkerStatus, datetime


class WorkerBase(BaseModel):
    employee_code: str = Field(min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    name: str = Field(min_length=1, max_length=100)
    department_id: int = Field(gt=0)
    phone: str | None = Field(default=None, max_length=15)
    status: WorkerStatus = "ACTIVE"


class WorkerCreate(WorkerBase):
    pass


class WorkerUpdate(BaseModel):
    employee_code: str | None = Field(default=None, min_length=1, max_length=20, pattern=r"^[A-Za-z0-9_-]+$")
    name: str | None = Field(default=None, min_length=1, max_length=100)
    department_id: int | None = Field(default=None, gt=0)
    phone: str | None = Field(default=None, max_length=15)
    status: WorkerStatus | None = None


class WorkerRead(WorkerBase, OrmModel):
    worker_id: int
    created_at: datetime
