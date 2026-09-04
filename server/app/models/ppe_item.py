from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class PpeItem(Base):
    __tablename__ = "ppe_items"
    __table_args__ = (
        CheckConstraint("name IN ('Helmet', 'Vest', 'Boots')", name="ck_ppe_items_name"),
    )

    ppe_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    is_mandatory: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    worker_assignments = relationship("WorkerPpe", back_populates="ppe_item")
    detections = relationship("PpeDetection", back_populates="ppe_item")
