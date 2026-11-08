import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.config import settings
from app.routers import clusters, index, search
from app.services import clip_service, qdrant_service

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Load CLIP model and ensure Qdrant collection on startup."""
    logger.info("Starting FamilyLens API...")
    try:
        clip_service.load_model()
        qdrant_service.ensure_collection()
    except Exception:
        logger.exception("Failed to initialize FamilyLens API")
        raise
    logger.info("FamilyLens API ready")
    yield
    logger.info("Shutting down FamilyLens API")


app = FastAPI(
    title="FamilyLens API",
    description="Local-first intelligent photo search",
    version="0.2.0",
    lifespan=lifespan,
)

app.include_router(index.router, prefix="/api")
app.include_router(clusters.router, prefix="/api")
app.include_router(search.router, prefix="/api")


@app.get("/health", response_model=None)
def health_check() -> dict:
    """Return dependency-aware health information."""
    dependencies = {
        "clip": "up" if clip_service.is_model_loaded() else "down",
        "qdrant": "up",
    }

    try:
        qdrant_service.check_health()
    except Exception:
        logger.exception("Qdrant health check failed")
        dependencies["qdrant"] = "down"

    status = (
        "ok" if all(value == "up" for value in dependencies.values()) else "degraded"
    )
    body = {
        "status": status,
        "dependencies": dependencies,
    }
    if status == "ok":
        return body
    return JSONResponse(status_code=503, content=body)
