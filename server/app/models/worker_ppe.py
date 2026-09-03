from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class WorkerPpe(Base):
    __tablename__ = "worker_ppe"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE', 'EXPIRED')", name="ck_worker_ppe_status"),
        UniqueConstraint("worker_id", "ppe_id", "serial_number", name="uq_worker_ppe_worker_item_serial"),
    )

    worker_ppe_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    worker_id: Mapped[int] = mapped_column(ForeignKey("workers.worker_id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False, index=True)
    ppe_id: Mapped[int] = mapped_column(ForeignKey("ppe_items.ppe_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True)
    rfid_tag: Mapped[str | None] = mapped_column(String(50))
    serial_number: Mapped[str | None] = mapped_column(String(50))
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    expiry_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")

    worker = relationship("Worker", back_populates="ppe_assignments")
    ppe_item = relationship("PpeItem", back_populates="worker_assignments")
