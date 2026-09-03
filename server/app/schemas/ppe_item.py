from pydantic import BaseModel, Field

from app.schemas.common import OrmModel, datetime


class PpeItemBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    is_mandatory: bool = True


class PpeItemCreate(PpeItemBase):
    pass


class PpeItemUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    is_mandatory: bool | None = None


class PpeItemRead(PpeItemBase, OrmModel):
    ppe_id: int
    created_at: datetime
