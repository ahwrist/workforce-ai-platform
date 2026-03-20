from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/survey", tags=["survey"])


@router.post("/session")
async def create_session():
    """Start a new survey session."""
    return {"data": None, "meta": {"version": "1.0"}, "error": {"code": "NOT_IMPLEMENTED", "message": "Phase 1f"}}


@router.post("/message")
async def send_message():
    """Send a message to the Interviewer agent."""
    return {"data": None, "meta": {"version": "1.0"}, "error": {"code": "NOT_IMPLEMENTED", "message": "Phase 1f"}}
