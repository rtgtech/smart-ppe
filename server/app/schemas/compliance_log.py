from pydantic import BaseModel, Field

from app.schemas.common import ComplianceStatus, Latitude, Longitude, OrmModel, Score, SyncStatus, datetime


class ComplianceLogBase(BaseModel):
    worker_id: int = Field(gt=0)
    gate_id: int = Field(gt=0)
    entry_time: datetime
    exit_time: datetime | None = None
    overall_status: ComplianceStatus
    compliance_score: Score
    confidence_score: Score | None = None
    image_url: str | None = None
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    offline_flag: bool = False
    sync_status: SyncStatus = "PENDING"


class ComplianceLogCreate(ComplianceLogBase):
    pass


class ComplianceLogUpdate(BaseModel):
    worker_id: int | None = Field(default=None, gt=0)
    gate_id: int | None = Field(default=None, gt=0)
    entry_time: datetime | None = None
    exit_time: datetime | None = None
    overall_status: ComplianceStatus | None = None
    compliance_score: Score | None = None
    confidence_score: Score | None = None
    image_url: str | None = None
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    offline_flag: bool | None = None
    sync_status: SyncStatus | None = None


class ComplianceLogRead(ComplianceLogBase, OrmModel):
    log_id: int
    created_at: datetime
