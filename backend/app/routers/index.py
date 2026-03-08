import logging
import threading
import time
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel

from app.config import settings
from app.services import clip_service, qdrant_service

logger = logging.getLogger(__name__)
router = APIRouter()

SUPPORTED_EXTENSIONS = clip_service.SUPPORTED_IMAGE_EXTENSIONS

# ---------------------------------------------------------------------------
# Module-level progress state, shared between the background worker and the
# status endpoint. Python's GIL ensures individual dict-key writes are
# atomic for simple types, which is sufficient here.
# ---------------------------------------------------------------------------
_progress: dict = {
    "status": "idle",  # idle | running | cancelling | complete | error | cancelled
    "current": 0,
    "total": 0,
    "indexed": 0,
    "skipped": 0,
    "errors": 0,
    "removed": 0,
    "started_at": 0.0,  # internal – time.monotonic() of run start
    "elapsed_seconds": 0.0,
    "eta_seconds": None,
    "result": None,
}
_cancel_event = threading.Event()
_run_lock = threading.Lock()


class IndexRequest(BaseModel):
    """Request body for the index endpoint."""

    folder: str | None = None
    cleanup: bool = False


class IndexResponse(BaseModel):
    """Response body for a completed indexing run."""

    indexed: int
    skipped: int
    errors: int
    removed: int
    total_in_collection: int


class IndexStatus(BaseModel):
    """Live status of the current (or last) indexing run."""

    status: str
    current: int
    total: int
    indexed: int
    skipped: int
    errors: int
    removed: int
    elapsed_seconds: float
    eta_seconds: float | None
    result: IndexResponse | None


def _discover_images(folder: Path) -> list[Path]:
    """Recursively find all supported image files."""
    images = []
    for ext in SUPPORTED_EXTENSIONS:
        images.extend(folder.rglob(f"*{ext}"))
        images.extend(folder.rglob(f"*{ext.upper()}"))
    return sorted(set(images))


def _run_indexing(folder: Path, cleanup: bool = False) -> None:
    """Background worker: index images and update _progress after every file.

    Checks _cancel_event before each file so the run can be interrupted.
    Always releases _run_lock on exit (acquired by the endpoint).
    """
    started_at = time.monotonic()
    _progress.update(
        {
            "status": "running",
            "current": 0,
            "total": 0,
            "indexed": 0,
            "skipped": 0,
            "errors": 0,
            "removed": 0,
            "started_at": started_at,
            "elapsed_seconds": 0.0,
            "eta_seconds": None,
            "result": None,
        }
    )
    try:
        if not folder.is_dir():
            logger.error("Folder not found: %s", folder)
            _progress["status"] = "error"
            return

        logger.info("Discovering images in %s", folder)
        image_paths = _discover_images(folder)
        logger.info("Found %d image files", len(image_paths))

        already_indexed = qdrant_service.get_indexed_paths()

        new_paths = [
            p for p in image_paths if str(p.relative_to(folder)) not in already_indexed
        ]
        skipped = len(image_paths) - len(new_paths)
        _progress["total"] = len(new_paths)
        _progress["skipped"] = skipped

        removed = 0
        if cleanup:
            disk_paths = {str(p.relative_to(folder)) for p in image_paths}
            stale = already_indexed - disk_paths
            if stale:
                removed = qdrant_service.delete_by_paths(list(stale))
                logger.info("Removed %d stale entries from index", removed)
        _progress["removed"] = removed

        indexed = 0
        errors = 0
        current = 0
        batch: list[tuple[str, str, list[float]]] = []

        for img_path in new_paths:
            if _cancel_event.is_set():
                logger.info("Indexing cancelled at %d/%d", current, len(new_paths))
                _progress.update(
                    {
                        "status": "cancelled",
                        "current": current,
                        "indexed": indexed,
                        "errors": errors,
                        "removed": removed,
                        "elapsed_seconds": time.monotonic() - started_at,
                        "eta_seconds": None,
                    }
                )
                return

            relative_path = str(img_path.relative_to(folder))
            try:
                embedding = clip_service.encode_image(img_path)
                batch.append((relative_path, img_path.name, embedding))
                indexed += 1
            except Exception:
                logger.exception("Failed to index %s", img_path)
                errors += 1

            current += 1
            elapsed = time.monotonic() - started_at
            rate = current / elapsed if elapsed > 0 else 0
            eta = (len(new_paths) - current) / rate if rate > 0 else None
            _progress.update(
                {
                    "current": current,
                    "indexed": indexed,
                    "errors": errors,
                    "elapsed_seconds": elapsed,
                    "eta_seconds": eta,
                }
            )

            if len(batch) >= settings.index_batch_size:
                qdrant_service.upsert_embeddings(batch)
                logger.info("Upserted batch of %d", len(batch))
                batch = []

        if batch:
            qdrant_service.upsert_embeddings(batch)
            logger.info("Upserted final batch of %d", len(batch))

        total_in_collection = qdrant_service.get_indexed_count()
        elapsed = time.monotonic() - started_at
        logger.info(
            "Indexing complete: %d indexed, %d skipped, %d errors",
            indexed,
            skipped,
            errors,
        )
        result = IndexResponse(
            indexed=indexed,
            skipped=skipped,
            errors=errors,
            removed=removed,
            total_in_collection=total_in_collection,
        )
        _progress.update(
            {
                "status": "complete",
                "current": len(new_paths),
                "indexed": indexed,
                "errors": errors,
                "elapsed_seconds": elapsed,
                "eta_seconds": None,
                "result": result,
            }
        )

    except Exception:
        logger.exception("Unexpected error during indexing")
        _progress.update(
            {
                "status": "error",
                "elapsed_seconds": time.monotonic() - started_at,
                "eta_seconds": None,
            }
        )
    finally:
        _run_lock.release()


@router.post("/index", response_model=IndexStatus)
def index_photos(
    background_tasks: BackgroundTasks,
    request: IndexRequest | None = None,
) -> IndexStatus:
    """Start indexing photos in the background.

    Returns immediately with status='running'. Poll GET /api/index/status
    for live progress. Returns 409 if indexing is already in progress.
    """
    folder = Path(request.folder if request and request.folder else settings.photos_dir)
    cleanup = request.cleanup if request else False

    if not _run_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Indexing already running")

    _cancel_event.clear()
    background_tasks.add_task(_run_indexing, folder, cleanup)

    return IndexStatus(
        status="running",
        current=0,
        total=0,
        indexed=0,
        skipped=0,
        errors=0,
        removed=0,
        elapsed_seconds=0.0,
        eta_seconds=None,
        result=None,
    )


@router.get("/index/status", response_model=IndexStatus)
async def get_index_status() -> IndexStatus:
    """Return the live status of the current (or last) indexing run."""
    p = _progress
    elapsed = p["elapsed_seconds"]
    if p["status"] == "running" and p["started_at"]:
        elapsed = time.monotonic() - p["started_at"]
    return IndexStatus(
        status=p["status"],
        current=p["current"],
        total=p["total"],
        indexed=p["indexed"],
        skipped=p["skipped"],
        errors=p["errors"],
        removed=p["removed"],
        elapsed_seconds=elapsed,
        eta_seconds=p["eta_seconds"],
        result=p["result"],
    )


@router.post("/index/cancel")
async def cancel_indexing() -> dict:
    """Request cancellation of the currently running indexing job."""
    if _progress["status"] not in ("running", "cancelling"):
        return {"status": _progress["status"]}
    _cancel_event.set()
    _progress["status"] = "cancelling"
    return {"status": "cancelling"}
