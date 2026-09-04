from pydantic import BaseModel, Field

from app.schemas.common import DetectionSource, OrmModel, Score, datetime


class PpeDetectionBase(BaseModel):
    log_id: int = Field(gt=0)
    ppe_id: int = Field(gt=0)
    detected: bool
    confidence_score: Score | None = None
    bounding_box: str | None = None
    detection_source: DetectionSource
    evidence_state: str | None = None
    observed_identifier: str | None = None
    assignment_result: str | None = None


class PpeDetectionCreate(PpeDetectionBase):
    pass


class PpeDetectionUpdate(BaseModel):
    log_id: int | None = Field(default=None, gt=0)
    ppe_id: int | None = Field(default=None, gt=0)
    detected: bool | None = None
    confidence_score: Score | None = None
    bounding_box: str | None = None
    detection_source: DetectionSource | None = None


class PpeDetectionRead(PpeDetectionBase, OrmModel):
    detection_id: int
    created_at: datetime
