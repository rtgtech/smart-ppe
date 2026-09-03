from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Device(Base):
    __tablename__ = "devices"
    __table_args__ = (
        CheckConstraint("device_type IN ('AI_CAMERA', 'RFID_READER', 'NFC_READER', 'GAS_SENSOR', 'GATE_CONTROLLER')", name="ck_devices_device_type"),
        CheckConstraint("status IN ('ONLINE', 'OFFLINE', 'MAINTENANCE')", name="ck_devices_status"),
        CheckConstraint("battery_level IS NULL OR (battery_level >= 0 AND battery_level <= 100)", name="ck_devices_battery_level"),
    )

    device_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    gate_id: Mapped[int] = mapped_column(ForeignKey("gates.gate_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True)
    device_type: Mapped[str] = mapped_column(String(30), nullable=False)
    serial_number: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ONLINE")
    last_seen: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    battery_level: Mapped[int | None] = mapped_column(Integer)
    firmware_version: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    gate = relationship("Gate", back_populates="devices")
