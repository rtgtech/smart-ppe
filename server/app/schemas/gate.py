from pydantic import BaseModel, Field

from app.schemas.common import GateStatus, Latitude, Longitude, OrmModel, datetime


class GateBase(BaseModel):
    mine_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=100)
    location: str = Field(min_length=1, max_length=150)
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    status: GateStatus = "ACTIVE"


class GateCreate(GateBase):
    pass


class GateUpdate(BaseModel):
    mine_id: int | None = Field(default=None, gt=0)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    location: str | None = Field(default=None, min_length=1, max_length=150)
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    status: GateStatus | None = None


class GateRead(GateBase, OrmModel):
    gate_id: int
    created_at: datetime
