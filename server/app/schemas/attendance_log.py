from pydantic import BaseModel, Field

from app.schemas.common import AttendanceStatus, OrmModel, datetime


class AttendanceLogBase(BaseModel):
    worker_id: int = Field(gt=0)
    gate_id: int = Field(gt=0)
    entry_time: datetime
    exit_time: datetime | None = None
    status: AttendanceStatus


class AttendanceLogCreate(AttendanceLogBase):
    pass


class AttendanceLogUpdate(BaseModel):
    worker_id: int | None = Field(default=None, gt=0)
    gate_id: int | None = Field(default=None, gt=0)
    entry_time: datetime | None = None
    exit_time: datetime | None = None
    status: AttendanceStatus | None = None


class AttendanceLogRead(AttendanceLogBase, OrmModel):
    attendance_id: int
    created_at: datetime
