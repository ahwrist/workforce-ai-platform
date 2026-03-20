from fastapi import APIRouter, Header, HTTPException

router = APIRouter(prefix="/api/v1/admin", tags=["admin"])


@router.post("/harvest/trigger")
async def trigger_harvest(x_admin_key: str = Header(...)):
    """Manually trigger the Harvester agent."""
    return {"data": {"message": "Harvest triggered"}, "meta": {"version": "1.0"}, "error": None}


@router.post("/synthesize/trigger")
async def trigger_synthesize(x_admin_key: str = Header(...)):
    """Manually trigger the Synthesizer agent."""
    return {"data": {"message": "Synthesis triggered"}, "meta": {"version": "1.0"}, "error": None}


@router.post("/classify/trigger")
async def trigger_classify(x_admin_key: str = Header(...)):
    """Manually trigger the Taxonomist agent."""
    return {"data": {"message": "Classification triggered"}, "meta": {"version": "1.0"}, "error": None}
