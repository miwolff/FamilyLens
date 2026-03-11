import logging
import threading
import time
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

from app.config import settings
from app.services import clip_service, clustering_service, qdrant_service

logger = logging.getLogger(__name__)
router = APIRouter()

SUPPORTED_EXTENSIONS = clip_service.SUPPORTED_IMAGE_EXTENSIONS
PROGRESS_TERMINAL_STATUSES = {"complete", "error", "cancelled"}
PHOTOS_ROOT = Path(settings.photos_dir).resolve()


def _make_default_progress_state() -> dict:
    """Return a fresh default indexing progress payload."""
    return {
        "status": "idle",  # idle | running | cancelling | complete | error | cancelled
        "stage": "idle",  # idle | discovering | indexing | clustering | complete
        "current": 0,
        "total": 0,
        "indexed": 0,
        "skipped": 0,
        "errors": 0,
        "removed": 0,
        "started_at": 0.0,  # internal – time.monotonic() of run start
        "elapsed_seconds": 0.0,
        "eta_seconds": None,
        "cluster_error": None,
        "cluster_count": settings.cluster_count,
        "result": None,
    }

# ---------------------------------------------------------------------------
# Module-level progress state, shared between the background worker and the
# status endpoint. Python's GIL ensures individual dict-key writes are
# atomic for simple types, which is sufficient here.
# ---------------------------------------------------------------------------
_progress: dict = _make_default_progress_state()
_progress_lock = threading.Lock()
_cancel_event = threading.Event()
_run_lock = threading.Lock()


def _update_progress(values: dict) -> None:
    """Apply a partial update to the shared progress state."""
    with _progress_lock:
        _progress.update(values)


def _replace_progress(values: dict | None = None) -> None:
    """Replace the shared progress state with a fresh snapshot."""
    next_progress = _make_default_progress_state()
    if values:
        next_progress.update(values)
    with _progress_lock:
        _progress.clear()
        _progress.update(next_progress)


def _set_progress_value(key: str, value: object) -> None:
    """Update a single progress field safely."""
    with _progress_lock:
        _progress[key] = value


def _get_progress_value(key: str) -> object:
    """Read a single progress field safely."""
    with _progress_lock:
        return _progress[key]


def reset_progress_state() -> None:
    """Reset the shared progress state to its default values."""
    _replace_progress()


def set_progress_state(values: dict) -> None:
    """Replace the shared progress state for tests or recovery flows."""
    _replace_progress(values)


def _resolve_index_folder(folder: str | None) -> Path:
    """Resolve an optional request folder to a safe path under the photos root."""
    if not folder:
        return PHOTOS_ROOT

    requested = Path(folder)
    resolved = (
        requested.resolve()
        if requested.is_absolute()
        else (PHOTOS_ROOT / requested).resolve()
    )
    if not resolved.is_relative_to(PHOTOS_ROOT):
        raise HTTPException(
            status_code=403,
            detail="Folder must stay within the configured photos directory",
        )
    return resolved


class IndexRequest(BaseModel):
    """Request body for the index endpoint."""

    folder: str | None = None
    cleanup: bool = False
    cluster_count: int = Field(
        default=settings.cluster_count,
        ge=1,
        le=settings.max_cluster_count,
    )


class IndexResponse(BaseModel):
    """Response body for a completed indexing run."""

    indexed: int
    skipped: int
    errors: int
    removed: int
    total_in_collection: int
    total_clusters: int


class IndexStatus(BaseModel):
    """Live status of the current (or last) indexing run."""

    status: str
    stage: str
    current: int
    total: int
    indexed: int
    skipped: int
    errors: int
    removed: int
    elapsed_seconds: float
    eta_seconds: float | None
    cluster_error: str | None
    cluster_count: int
    result: IndexResponse | None


def get_progress_snapshot() -> dict:
    """Return a safe snapshot of the current indexing progress."""
    with _progress_lock:
        progress = dict(_progress)
    if progress["status"] == "running" and progress["started_at"]:
        progress["elapsed_seconds"] = (
            time.monotonic() - progress["started_at"]
        )
    return progress


def _discover_images(folder: Path) -> list[Path]:
    """Recursively find all supported image files."""
    images = []
    for ext in SUPPORTED_EXTENSIONS:
        images.extend(folder.rglob(f"*{ext}"))
        images.extend(folder.rglob(f"*{ext.upper()}"))
    return sorted(set(images))


def _run_indexing(
    folder: Path,
    cleanup: bool = False,
    cluster_count: int = settings.cluster_count,
) -> None:
    """Background worker: index images and update _progress after every file.

    Checks _cancel_event before each file so the run can be interrupted.
    Always releases _run_lock on exit (acquired by the endpoint).
    """
    started_at = time.monotonic()
    _replace_progress(
        {
            "status": "running",
            "stage": "discovering",
            "current": 0,
            "total": 0,
            "indexed": 0,
            "skipped": 0,
            "errors": 0,
            "removed": 0,
            "started_at": started_at,
            "elapsed_seconds": 0.0,
            "eta_seconds": None,
            "cluster_error": None,
            "cluster_count": cluster_count,
            "result": None,
        }
    )
    try:
        if not folder.is_dir():
            logger.error("Folder not found: %s", folder)
            _update_progress({"status": "error", "stage": "error"})
            return

        logger.info("Discovering images in %s", folder)
        image_paths = _discover_images(folder)
        logger.info("Found %d image files", len(image_paths))

        already_indexed = qdrant_service.get_indexed_paths()

        new_paths = [
            p for p in image_paths if str(p.relative_to(folder)) not in already_indexed
        ]
        skipped = len(image_paths) - len(new_paths)
        _update_progress(
            {
                "stage": "indexing",
                "total": len(new_paths),
                "skipped": skipped,
            }
        )

        removed = 0
        if cleanup:
            disk_paths = {str(p.relative_to(folder)) for p in image_paths}
            stale = already_indexed - disk_paths
            if stale:
                removed = qdrant_service.delete_by_paths(list(stale))
                logger.info("Removed %d stale entries from index", removed)
        _set_progress_value("removed", removed)

        indexed = 0
        errors = 0
        current = 0
        batch: list[tuple[str, str, list[float]]] = []

        for img_path in new_paths:
            if _cancel_event.is_set():
                logger.info("Indexing cancelled at %d/%d", current, len(new_paths))
                _update_progress(
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
            _update_progress(
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

        if _cancel_event.is_set():
            logger.info("Indexing cancelled before clustering started")
            _update_progress(
                {
                    "status": "cancelled",
                    "stage": "cancelled",
                    "current": current,
                    "indexed": indexed,
                    "errors": errors,
                    "removed": removed,
                    "elapsed_seconds": time.monotonic() - started_at,
                    "eta_seconds": None,
                }
            )
            return

        _update_progress(
            {
                "stage": "clustering",
                "current": len(new_paths),
                "eta_seconds": None,
            }
        )

        total_clusters = 0
        cluster_error = None
        try:
            cluster_result = clustering_service.rebuild_clusters(
                cluster_count=cluster_count,
                is_cancelled=_cancel_event.is_set,
            )
            total_clusters = cluster_result.total_clusters
        except clustering_service.ClusteringCancelledError:
            logger.info("Cluster build cancelled")
            _update_progress(
                {
                    "status": "cancelled",
                    "stage": "cancelled",
                    "elapsed_seconds": time.monotonic() - started_at,
                    "eta_seconds": None,
                }
            )
            return
        except Exception as exc:
            logger.exception("Cluster build failed")
            cluster_error = str(exc) or "Clusters could not be updated."

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
            total_clusters=total_clusters,
        )
        _update_progress(
            {
                "status": "complete",
                "stage": "complete",
                "current": len(new_paths),
                "indexed": indexed,
                "errors": errors,
                "elapsed_seconds": elapsed,
                "eta_seconds": None,
                "cluster_error": cluster_error,
                "result": result,
            }
        )

    except Exception:
        logger.exception("Unexpected error during indexing")
        _update_progress(
            {
                "status": "error",
                "stage": "error",
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
    folder = _resolve_index_folder(request.folder if request else None)
    cleanup = request.cleanup if request else False
    cluster_count = request.cluster_count if request else settings.cluster_count

    if not _run_lock.acquire(blocking=False):
        raise HTTPException(status_code=409, detail="Indexing already running")

    _cancel_event.clear()
    background_tasks.add_task(_run_indexing, folder, cleanup, cluster_count)

    return IndexStatus(
        status="running",
        stage="discovering",
        current=0,
        total=0,
        indexed=0,
        skipped=0,
        errors=0,
        removed=0,
        elapsed_seconds=0.0,
        eta_seconds=None,
        cluster_error=None,
        cluster_count=cluster_count,
        result=None,
    )


@router.get("/index/status", response_model=IndexStatus)
async def get_index_status() -> IndexStatus:
    """Return the live status of the current (or last) indexing run."""
    p = get_progress_snapshot()
    return IndexStatus(
        status=p["status"],
        stage=p["stage"],
        current=p["current"],
        total=p["total"],
        indexed=p["indexed"],
        skipped=p["skipped"],
        errors=p["errors"],
        removed=p["removed"],
        elapsed_seconds=p["elapsed_seconds"],
        eta_seconds=p["eta_seconds"],
        cluster_error=p["cluster_error"],
        cluster_count=p["cluster_count"],
        result=p["result"],
    )


@router.post("/index/cancel")
async def cancel_indexing() -> dict:
    """Request cancellation of the currently running indexing job."""
    progress = get_progress_snapshot()
    if progress["status"] not in ("running", "cancelling"):
        return {
            "status": progress["status"],
            "cluster_count": progress["cluster_count"],
        }
    _cancel_event.set()
    _update_progress(
        {
            "status": "cancelling",
            "stage": progress["stage"] or "cancelling",
        }
    )
    return {
        "status": "cancelling",
        "cluster_count": progress["cluster_count"],
    }
