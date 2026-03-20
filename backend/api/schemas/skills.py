import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class SkillResponse(BaseModel):
    id: uuid.UUID
    canonical_name: str
    description: Optional[str] = None
    skill_type: Optional[str] = None
    domain: Optional[str] = None
    subdomain: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class PaginatedSkills(BaseModel):
    items: list[SkillResponse]
    next_cursor: Optional[str] = None
    has_more: bool
    total: int


class TrendingSkillItem(BaseModel):
    skill: SkillResponse
    posting_count: int
    domain: Optional[str] = None


class DomainResponse(BaseModel):
    domain: str
    label: str
    skill_count: int
