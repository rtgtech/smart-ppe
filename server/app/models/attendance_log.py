from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class AttendanceLog(Base):
    __tablename__ = "attendance_logs"
    __table_args__ = (
        CheckConstraint("status IN ('PRESENT', 'INSIDE', 'OUTSIDE', 'ABSENT')", name="ck_attendance_logs_status"),
        CheckConstraint("data_origin IN ('LIVE', 'MANUAL', 'DEMO', 'IMPORTED')", name="ck_attendance_logs_data_origin"),
        Index("ix_attendance_worker_entry", "worker_id", "entry_time"),
    )

    attendance_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[str | None] = mapped_column(String(36), unique=True, index=True)
    worker_id: Mapped[int] = mapped_column(ForeignKey("workers.worker_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True)
    gate_id: Mapped[int] = mapped_column(ForeignKey("gates.gate_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True)
    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    exit_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    data_origin: Mapped[str] = mapped_column(String(16), nullable=False, default="IMPORTED", server_default="IMPORTED", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    worker = relationship("Worker", back_populates="attendance_logs")
    gate = relationship("Gate", back_populates="attendance_logs")
