from pydantic import BaseModel, Field, model_validator

from app.schemas.common import AlertSeverity, AlertStatus, OrmModel, datetime


class AlertBase(BaseModel):
    event_id: str | None = None
    gate_id: int | None = Field(default=None, gt=0)
    log_id: int | None = Field(default=None, gt=0)
    worker_id: int | None = Field(default=None, gt=0)
    alert_type: str = Field(min_length=1, max_length=50)
    severity: AlertSeverity
    message: str = Field(min_length=1)
    status: AlertStatus = "ACTIVE"
    resolved_at: datetime | None = None

    @model_validator(mode="after")
    def validate_resolved_status(self):
        if self.resolved_at is not None and self.status not in {"RESOLVED", "CLOSED"}:
            raise ValueError("resolved_at can only be set for RESOLVED or CLOSED alerts")
        return self


class AlertCreate(AlertBase):
    pass


class AlertUpdate(BaseModel):
    log_id: int | None = Field(default=None, gt=0)
    worker_id: int | None = Field(default=None, gt=0)
    alert_type: str | None = Field(default=None, min_length=1, max_length=50)
    severity: AlertSeverity | None = None
    message: str | None = Field(default=None, min_length=1)
    status: AlertStatus | None = None
    resolved_at: datetime | None = None


class AlertRead(AlertBase, OrmModel):
    alert_id: int
    created_at: datetime
