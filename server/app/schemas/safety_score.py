from pydantic import BaseModel, Field

from app.schemas.common import OrmModel, RiskLevel, Score, datetime


class SafetyScoreBase(BaseModel):
    worker_id: int = Field(gt=0)
    score: Score
    risk_level: RiskLevel
    violation_count: int = Field(ge=0)
    compliance_rate: Score


class SafetyScoreCreate(SafetyScoreBase):
    pass


class SafetyScoreUpdate(BaseModel):
    worker_id: int | None = Field(default=None, gt=0)
    score: Score | None = None
    risk_level: RiskLevel | None = None
    violation_count: int | None = Field(default=None, ge=0)
    compliance_rate: Score | None = None


class SafetyScoreRead(SafetyScoreBase, OrmModel):
    score_id: int
    calculated_at: datetime
