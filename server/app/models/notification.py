from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Notification(Base):
    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint("channel IN ('SMS', 'EMAIL', 'PUSH', 'APP')", name="ck_notifications_channel"),
        CheckConstraint("status IN ('SENT', 'FAILED', 'PENDING')", name="ck_notifications_status"),
    )

    notification_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    alert_id: Mapped[int] = mapped_column(ForeignKey("alerts.alert_id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False, index=True)
    recipient_id: Mapped[int] = mapped_column(nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    alert = relationship("Alert", back_populates="notifications")
