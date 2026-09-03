from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Worker(Base):
    __tablename__ = "workers"
    __table_args__ = (
        CheckConstraint("status IN ('ACTIVE', 'INACTIVE')", name="ck_workers_status"),
    )

    worker_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    employee_code: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    photo_url: Mapped[str | None] = mapped_column(Text)
    department_id: Mapped[int] = mapped_column(ForeignKey("departments.department_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True)
    designation: Mapped[str | None] = mapped_column(String(100))
    phone: Mapped[str | None] = mapped_column(String(15))
    email: Mapped[str | None] = mapped_column(String(100))
    rfid_uid: Mapped[str | None] = mapped_column(String(50), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    department = relationship("Department", back_populates="workers")
    ppe_assignments = relationship("WorkerPpe", back_populates="worker", cascade="all, delete-orphan")
    compliance_logs = relationship("ComplianceLog", back_populates="worker")
    attendance_logs = relationship("AttendanceLog", back_populates="worker")
    alerts = relationship("Alert", back_populates="worker")
    safety_scores = relationship("SafetyScore", back_populates="worker", cascade="all, delete-orphan")
    generated_reports = relationship("Report", back_populates="generator")
