import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.routers import index, search
from app.services import clip_service, qdrant_service

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Load CLIP model and ensure Qdrant collection on startup."""
    logger.info("Starting FamilyLens API...")
    clip_service.load_model()
    qdrant_service.ensure_collection()
    logger.info("FamilyLens API ready")
    yield
    logger.info("Shutting down FamilyLens API")


app = FastAPI(
    title="FamilyLens API",
    description="Local-first intelligent photo search",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(index.router, prefix="/api")
app.include_router(search.router, prefix="/api")


@app.get("/health")
def health_check() -> dict:
    """Simple health check endpoint."""
    return {"status": "ok"}
