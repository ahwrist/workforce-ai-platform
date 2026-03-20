from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/skills", tags=["skills"])


@router.get("/")
async def list_skills():
    """List skills with optional domain filter."""
    return {"data": {"items": [], "total": 0}, "meta": {"version": "1.0"}, "error": None}


@router.get("/trending")
async def get_trending_skills(domain: str | None = None, days: int = 30):
    """Get trending skills by frequency in recent job postings."""
    return {"data": {"items": [], "domain": domain, "days": days}, "meta": {"version": "1.0"}, "error": None}


@router.get("/{skill_id}")
async def get_skill(skill_id: str):
    """Get skill detail with similar skills from Qdrant."""
    return {"data": None, "meta": {"version": "1.0"}, "error": {"code": "NOT_IMPLEMENTED", "message": "Phase 1e"}}
