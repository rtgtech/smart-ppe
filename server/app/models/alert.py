from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Alert(Base):
    __tablename__ = "alerts"
    __table_args__ = (
        CheckConstraint("severity IN ('INFO', 'WARNING', 'CRITICAL')", name="ck_alerts_severity"),
        CheckConstraint("status IN ('ACTIVE', 'RESOLVED', 'CLOSED')", name="ck_alerts_status"),
        CheckConstraint("resolved_at IS NULL OR status IN ('RESOLVED', 'CLOSED')", name="ck_alerts_resolved_status"),
    )

    alert_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[str | None] = mapped_column(String(36), unique=True, index=True)
    gate_id: Mapped[int | None] = mapped_column(ForeignKey("gates.gate_id", ondelete="SET NULL"), index=True)
    log_id: Mapped[int | None] = mapped_column(ForeignKey("compliance_logs.log_id", ondelete="SET NULL", onupdate="CASCADE"), index=True)
    worker_id: Mapped[int | None] = mapped_column(ForeignKey("workers.worker_id", ondelete="SET NULL", onupdate="CASCADE"), index=True)
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    compliance_log = relationship("ComplianceLog", back_populates="alerts")
    worker = relationship("Worker", back_populates="alerts")
    gate = relationship("Gate")
