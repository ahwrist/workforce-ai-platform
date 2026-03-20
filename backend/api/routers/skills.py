import base64
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import JSONResponse
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas.skills import PaginatedSkills, SkillResponse, TrendingSkillItem
from core.database.postgres import get_db
from core.models.job_posting import JobPosting
from core.models.skill import JobPostingSkill, Skill

router = APIRouter(prefix="/api/v1/skills", tags=["skills"])

_META = {"version": "1.0"}


def _ok(data):
    return {"data": data, "meta": _META, "error": None}


def _err(code: str, message: str):
    return {"data": None, "meta": _META, "error": {"code": code, "message": message}}


def _encode_cursor(offset: int) -> str:
    return base64.urlsafe_b64encode(str(offset).encode()).decode()


def _decode_cursor(cursor: str) -> int:
    try:
        return int(base64.urlsafe_b64decode(cursor.encode()).decode())
    except Exception:
        return 0


@router.get("/")
async def list_skills(
    domain: Optional[str] = Query(None),
    cursor: Optional[str] = Query(None),
    limit: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Paginated list of skills with optional domain filter."""
    offset = _decode_cursor(cursor) if cursor else 0

    count_q = select(func.count()).select_from(Skill)
    if domain:
        count_q = count_q.where(Skill.domain == domain)
    total = (await db.execute(count_q)).scalar_one()

    q = select(Skill).order_by(Skill.canonical_name)
    if domain:
        q = q.where(Skill.domain == domain)
    q = q.offset(offset).limit(limit + 1)

    rows = (await db.execute(q)).scalars().all()
    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor = _encode_cursor(offset + limit) if has_more else None

    return _ok(
        PaginatedSkills(
            items=[SkillResponse.model_validate(s) for s in items],
            next_cursor=next_cursor,
            has_more=has_more,
            total=total,
        ).model_dump()
    )


@router.get("/trending")
async def get_trending_skills(
    domain: Optional[str] = Query(None),
    days: int = Query(30, ge=1),
    limit: int = Query(25, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Top N skills by job posting frequency in the last N days."""
    since = datetime.now(timezone.utc) - timedelta(days=days)

    q = (
        select(Skill, func.count(JobPostingSkill.id).label("posting_count"))
        .join(JobPostingSkill, Skill.id == JobPostingSkill.skill_id)
        .join(JobPosting, JobPostingSkill.job_posting_id == JobPosting.id)
        .where(JobPosting.harvested_at >= since)
        .group_by(Skill.id)
        .order_by(desc("posting_count"))
        .limit(limit)
    )
    if domain:
        q = q.where(Skill.domain == domain)

    rows = (await db.execute(q)).all()

    items = [
        TrendingSkillItem(
            skill=SkillResponse.model_validate(row[0]),
            posting_count=row[1],
            domain=row[0].domain,
        ).model_dump()
        for row in rows
    ]
    return _ok(items)


@router.get("/{skill_id}")
async def get_skill(skill_id: str, db: AsyncSession = Depends(get_db)):
    """Single skill detail by UUID."""
    try:
        skill_uuid = uuid.UUID(skill_id)
    except ValueError:
        return JSONResponse(
            status_code=404,
            content=_err("NOT_FOUND", f"Skill '{skill_id}' not found"),
        )

    skill = await db.get(Skill, skill_uuid)
    if skill is None:
        return JSONResponse(
            status_code=404,
            content=_err("NOT_FOUND", f"Skill '{skill_id}' not found"),
        )

    return _ok(SkillResponse.model_validate(skill).model_dump())
