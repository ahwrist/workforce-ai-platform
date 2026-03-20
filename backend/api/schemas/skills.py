import uuid
from datetime import datetime

from pydantic import BaseModel


class SkillResponse(BaseModel):
    id: uuid.UUID
    canonical_name: str
    skill_type: str | None
    domain: str | None
    subdomain: str | None
    created_at: datetime

    class Config:
        from_attributes = True
