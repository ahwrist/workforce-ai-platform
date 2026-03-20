from pathlib import Path
from typing import Optional

import yaml
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.skills import DomainResponse
from core.database.postgres import get_db
from core.models.skill import Skill

router = APIRouter(prefix="/api/v1/domains", tags=["domains"])

_META = {"version": "1.0"}
_TAXONOMY_PATH = Path(__file__).parent.parent.parent / "agents" / "taxonomist" / "taxonomy.yaml"


def _load_domain_labels() -> dict[str, str]:
    """Load domain → label mapping from taxonomy.yaml."""
    with open(_TAXONOMY_PATH) as f:
        taxonomy = yaml.safe_load(f)
    return {
        domain_key: domain_data.get("label", domain_key)
        for domain_key, domain_data in taxonomy.get("domains", {}).items()
    }


@router.get("/")
async def list_domains(db: AsyncSession = Depends(get_db)):
    """List all domains with their skill counts and human-readable labels."""
    domain_labels = _load_domain_labels()

    q = select(Skill.domain, func.count(Skill.id).label("skill_count")).group_by(Skill.domain)
    rows = (await db.execute(q)).all()

    # Build result from taxonomy order, merging in DB counts
    db_counts: dict[Optional[str], int] = {row[0]: row[1] for row in rows}

    result = [
        DomainResponse(
            domain=domain_key,
            label=label,
            skill_count=db_counts.get(domain_key, 0),
        ).model_dump()
        for domain_key, label in domain_labels.items()
    ]

    return {"data": result, "meta": _META, "error": None}
