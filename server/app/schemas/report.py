from pydantic import BaseModel, Field, model_validator

from app.schemas.common import OrmModel, ReportType, date, datetime


class ReportBase(BaseModel):
    report_type: ReportType
    period_start: date
    period_end: date
    generated_by: int | None = Field(default=None, gt=0)
    file_url: str | None = None

    @model_validator(mode="after")
    def validate_period(self):
        if self.period_end < self.period_start:
            raise ValueError("period_end must be greater than or equal to period_start")
        return self


class ReportCreate(ReportBase):
    pass


class ReportUpdate(BaseModel):
    report_type: ReportType | None = None
    period_start: date | None = None
    period_end: date | None = None
    generated_by: int | None = Field(default=None, gt=0)
    file_url: str | None = None

    @model_validator(mode="after")
    def validate_period(self):
        if self.period_start is not None and self.period_end is not None and self.period_end < self.period_start:
            raise ValueError("period_end must be greater than or equal to period_start")
        return self


class ReportRead(ReportBase, OrmModel):
    report_id: int
    generated_at: datetime
