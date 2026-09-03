from pydantic import BaseModel, Field

from app.schemas.common import DeviceStatus, DeviceType, OrmModel, datetime


class DeviceBase(BaseModel):
    gate_id: int = Field(gt=0)
    device_type: DeviceType
    serial_number: str = Field(min_length=1, max_length=100)
    status: DeviceStatus = "ONLINE"
    last_seen: datetime | None = None
    battery_level: int | None = Field(default=None, ge=0, le=100)
    firmware_version: str | None = Field(default=None, max_length=50)


class DeviceCreate(DeviceBase):
    pass


class DeviceUpdate(BaseModel):
    gate_id: int | None = Field(default=None, gt=0)
    device_type: DeviceType | None = None
    serial_number: str | None = Field(default=None, min_length=1, max_length=100)
    status: DeviceStatus | None = None
    last_seen: datetime | None = None
    battery_level: int | None = Field(default=None, ge=0, le=100)
    firmware_version: str | None = Field(default=None, max_length=50)


class DeviceRead(DeviceBase, OrmModel):
    device_id: int
    created_at: datetime
