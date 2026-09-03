from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Gate(Base):
    __tablename__ = "gates"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE', 'MAINTENANCE', 'OFFLINE')", name="ck_gates_status"),
        UniqueConstraint("mine_id", "name", name="uq_gates_mine_name"),
    )

    gate_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    mine_id: Mapped[int] = mapped_column(ForeignKey("mines.mine_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    location: Mapped[str] = mapped_column(String(150), nullable=False)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    mine = relationship("Mine", back_populates="gates")
    devices = relationship("Device", back_populates="gate")
    compliance_logs = relationship("ComplianceLog", back_populates="gate")
    attendance_logs = relationship("AttendanceLog", back_populates="gate")
