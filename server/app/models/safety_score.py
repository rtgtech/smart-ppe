from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Float, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class SafetyScore(Base):
    __tablename__ = "safety_scores"
    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 100", name="ck_safety_scores_score"),
        CheckConstraint("risk_level IN ('LOW', 'MEDIUM', 'HIGH')", name="ck_safety_scores_risk_level"),
        CheckConstraint("violation_count >= 0", name="ck_safety_scores_violation_count"),
        CheckConstraint("compliance_rate >= 0 AND compliance_rate <= 100", name="ck_safety_scores_compliance_rate"),
    )

    score_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    worker_id: Mapped[int] = mapped_column(ForeignKey("workers.worker_id", ondelete="CASCADE", onupdate="CASCADE"), nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(20), nullable=False)
    violation_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    compliance_rate: Mapped[float] = mapped_column(Float, nullable=False)
    calculated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), index=True)

    worker = relationship("Worker", back_populates="safety_scores")
