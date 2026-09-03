from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Report(Base):
    __tablename__ = "reports"
    __table_args__ = (
        CheckConstraint("report_type IN ('DAILY', 'WEEKLY', 'MONTHLY', 'WORKER_WISE', 'GATE_WISE', 'PPE_WISE')", name="ck_reports_report_type"),
        CheckConstraint("period_end >= period_start", name="ck_reports_period"),
    )

    report_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    report_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    period_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    period_end: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    generated_by: Mapped[int | None] = mapped_column(ForeignKey("workers.worker_id", ondelete="SET NULL", onupdate="CASCADE"), index=True)
    file_url: Mapped[str | None] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    generator = relationship("Worker", back_populates="generated_reports")
