from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import skills, survey, auth, admin
from core.config.settings import get_settings
from core.config.logging import configure_logging
from core.database.qdrant import ensure_collections

settings = get_settings()
configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: ensure Qdrant collections exist
    try:
        await ensure_collections()
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning(f"Qdrant collection setup failed (non-fatal): {exc}")
    yield
    # Shutdown: nothing to clean up for now


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:80"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(skills.router)
app.include_router(survey.router)
app.include_router(auth.router)
app.include_router(admin.router)


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "version": settings.app_version,
        "service": "workforce-ai-api",
    }
