from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/token")
async def login():
    """Issue a JWT token."""
    return {"data": None, "meta": {"version": "1.0"}, "error": {"code": "NOT_IMPLEMENTED", "message": "Phase 1e"}}
