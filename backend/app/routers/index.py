import logging
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import settings
from app.services import clip_service, qdrant_service

logger = logging.getLogger(__name__)
router = APIRouter()

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png"}


class IndexRequest(BaseModel):
    """Request body for the index endpoint."""

    folder: str | None = None


class IndexResponse(BaseModel):
    """Response body for the index endpoint."""

    indexed: int
    skipped: int
    errors: int
    total_in_collection: int


def _discover_images(folder: Path) -> list[Path]:
    """Recursively find all supported image files."""
    images = []
    for ext in SUPPORTED_EXTENSIONS:
        images.extend(folder.rglob(f"*{ext}"))
        images.extend(folder.rglob(f"*{ext.upper()}"))
    return sorted(set(images))


@router.post("/index", response_model=IndexResponse)
def index_photos(request: IndexRequest | None = None) -> IndexResponse:
    """Index photos from the configured or specified folder.

    Walks the folder recursively for JPEG/PNG files, encodes
    each with CLIP, and upserts embeddings into Qdrant.
    Already-indexed files are skipped.
    """
    folder = Path(request.folder if request and request.folder else settings.photos_dir)
    if not folder.is_dir():
        raise ValueError(f"Folder not found: {folder}")

    logger.info("Discovering images in %s", folder)
    image_paths = _discover_images(folder)
    logger.info("Found %d image files", len(image_paths))

    already_indexed = qdrant_service.get_indexed_paths()

    indexed = 0
    skipped = 0
    errors = 0
    batch: list[tuple[str, str, list[float]]] = []

    for img_path in image_paths:
        relative_path = str(img_path.relative_to(folder))

        if relative_path in already_indexed:
            skipped += 1
            continue

        try:
            embedding = clip_service.encode_image(img_path)
            batch.append((relative_path, img_path.name, embedding))
            indexed += 1

            if len(batch) >= settings.index_batch_size:
                qdrant_service.upsert_embeddings(batch)
                logger.info("Upserted batch of %d", len(batch))
                batch = []

        except Exception:
            logger.exception("Failed to index %s", img_path)
            errors += 1

    if batch:
        qdrant_service.upsert_embeddings(batch)
        logger.info("Upserted final batch of %d", len(batch))

    total = qdrant_service.get_indexed_count()
    logger.info(
        "Indexing complete: %d indexed, %d skipped, %d errors",
        indexed,
        skipped,
        errors,
    )

    return IndexResponse(
        indexed=indexed,
        skipped=skipped,
        errors=errors,
        total_in_collection=total,
    )
