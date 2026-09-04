from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, Float, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class GateEvent(Base):
    __tablename__ = "gate_events"
    __table_args__ = (
        CheckConstraint("lifecycle IN ('ACTIVE', 'FINALIZED', 'ABANDONED')", name="ck_gate_events_lifecycle"),
        CheckConstraint("verdict IS NULL OR verdict IN ('ALLOWED', 'DENIED', 'HOLD')", name="ck_gate_events_verdict"),
        CheckConstraint("sync_status IN ('PENDING', 'SYNCED', 'FAILED')", name="ck_gate_events_sync_status"),
    )

    event_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    worker_id: Mapped[int | None] = mapped_column(ForeignKey("workers.worker_id", ondelete="SET NULL"), index=True)
    gate_id: Mapped[int] = mapped_column(ForeignKey("gates.gate_id", ondelete="RESTRICT"), nullable=False, index=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("devices.device_id", ondelete="RESTRICT"), nullable=False, index=True)
    lifecycle: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE", index=True)
    verdict: Mapped[str | None] = mapped_column(String(16), index=True)
    gate_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    gate_longitude: Mapped[float] = mapped_column(Float, nullable=False)
    edge_timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    evidence_confidence: Mapped[float | None] = mapped_column(Float)
    reasons_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    qr_results_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    offline_flag: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sync_status: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING", index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())

    worker = relationship("Worker")
    gate = relationship("Gate")
    device = relationship("Device")
