from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Department(Base):
    __tablename__ = "departments"
    __table_args__ = (
        UniqueConstraint("mine_id", "name", name="uq_departments_mine_name"),
    )

    department_id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    mine_id: Mapped[int] = mapped_column(ForeignKey("mines.mine_id", ondelete="RESTRICT", onupdate="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    mine = relationship("Mine", back_populates="departments")
    workers = relationship("Worker", back_populates="department")
