from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PpeDetection(Base):
    __tablename__ = "ppe_detections"
    __table_args__ = (
        CheckConstraint("confidence_score IS NULL OR (confidence_score >= 0 AND confidence_score <= 100)", name="ck_ppe_detections_confidence_score"),
        CheckConstraint("detection_source IN ('AI', 'QR', 'RFID', 'SENSOR')", name="ck_ppe_detections_detection_source"),
        UniqueConstraint("log_id", "ppe_id", "detection_source", name="uq_ppe_detections_log_item_source"),
    )

    detection_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    log_id: Mapped[int] = mapped_column(ForeignKey("compliance_logs.log_id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False, index=True)
    ppe_id: Mapped[int] = mapped_column(ForeignKey("ppe_items.ppe_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True)
    detected: Mapped[bool] = mapped_column(Boolean, nullable=False)
    confidence_score: Mapped[float | None] = mapped_column(Float)
    detection_source: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    compliance_log = relationship("ComplianceLog", back_populates="detections")
    ppe_item = relationship("PpeItem", back_populates="detections")
