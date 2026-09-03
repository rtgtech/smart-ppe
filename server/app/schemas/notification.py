from pydantic import BaseModel, Field

from app.schemas.common import NotificationChannel, NotificationStatus, OrmModel, datetime


class NotificationBase(BaseModel):
    alert_id: int = Field(gt=0)
    recipient_id: int = Field(gt=0)
    channel: NotificationChannel
    message: str = Field(min_length=1)
    status: NotificationStatus = "PENDING"
    sent_at: datetime | None = None


class NotificationCreate(NotificationBase):
    pass


class NotificationUpdate(BaseModel):
    alert_id: int | None = Field(default=None, gt=0)
    recipient_id: int | None = Field(default=None, gt=0)
    channel: NotificationChannel | None = None
    message: str | None = Field(default=None, min_length=1)
    status: NotificationStatus | None = None
    sent_at: datetime | None = None


class NotificationRead(NotificationBase, OrmModel):
    notification_id: int
