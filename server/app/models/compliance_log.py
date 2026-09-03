from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ComplianceLog(Base):
    __tablename__ = "compliance_logs"
    __table_args__ = (
        CheckConstraint("overall_status IN ('COMPLIANT', 'NON_COMPLIANT', 'DENIED')", name="ck_compliance_logs_overall_status"),
        CheckConstraint("compliance_score >= 0 AND compliance_score <= 100", name="ck_compliance_logs_compliance_score"),
        CheckConstraint("confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 100)", name="ck_compliance_logs_confidence_score"),
        CheckConstraint("sync_status IN ('PENDING', 'SYNCED', 'FAILED')", name="ck_compliance_logs_sync_status"),
    )

    log_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    worker_id: Mapped[int] = mapped_column(ForeignKey("workers.worker_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True)
    gate_id: Mapped[int] = mapped_column(ForeignKey("gates.gate_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True)
    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    exit_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    overall_status: Mapped[str] = mapped_column(String(20), nullable=False)
    compliance_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float)
    image_url: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    offline_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sync_status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    worker = relationship("Worker", back_populates="compliance_logs")
    gate = relationship("Gate", back_populates="compliance_logs")
    detections = relationship("PpeDetection", back_populates="compliance_log", cascade="all, delete-orphan")
    alerts = relationship("Alert", back_populates="compliance_log")
