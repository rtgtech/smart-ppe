from pydantic import BaseModel, Field

from app.schemas.common import Latitude, Longitude, MineStatus, OrmModel, datetime


class MineBase(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    location: str = Field(min_length=1, max_length=150)
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    status: MineStatus = "ACTIVE"


class MineCreate(MineBase):
    pass


class MineUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    location: str | None = Field(default=None, min_length=1, max_length=150)
    latitude: Latitude | None = None
    longitude: Longitude | None = None
    status: MineStatus | None = None


class MineRead(MineBase, OrmModel):
    mine_id: int
    created_at: datetime
