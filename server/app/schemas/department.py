from pydantic import BaseModel, Field

from app.schemas.common import OrmModel, datetime


class DepartmentBase(BaseModel):
    mine_id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None


class DepartmentCreate(DepartmentBase):
    pass


class DepartmentUpdate(BaseModel):
    mine_id: int | None = Field(default=None, gt=0)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None


class DepartmentRead(DepartmentBase, OrmModel):
    department_id: int
    created_at: datetime
