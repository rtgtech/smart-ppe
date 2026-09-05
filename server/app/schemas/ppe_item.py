from typing import Literal

from pydantic import BaseModel

from app.schemas.common import OrmModel, datetime


class PpeItemBase(BaseModel):
    name: Literal["Gloves", "Goggles", "Helmet", "Mask", "Shoes", "Vest"]
    is_mandatory: Literal[True] = True


class PpeItemCreate(PpeItemBase):
    pass


class PpeItemUpdate(BaseModel):
    name: Literal["Gloves", "Goggles", "Helmet", "Mask", "Shoes", "Vest"] | None = None
    is_mandatory: Literal[True] | None = None


class PpeItemRead(PpeItemBase, OrmModel):
    ppe_id: int
    created_at: datetime
