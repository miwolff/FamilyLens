import logging
import mimetypes
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from app.config import settings
from app.services import clip_service, qdrant_service

logger = logging.getLogger(__name__)
router = APIRouter()


class SearchRequest(BaseModel):
    """Request body for the search endpoint."""

    query: str = Field(..., min_length=1, max_length=500)
    limit: int = Field(default=settings.search_default_limit, ge=1, le=100)


class SearchResult(BaseModel):
    """A single search result."""

    file_path: str
    filename: str
    score: float


class SearchResponse(BaseModel):
    """Response body for the search endpoint."""

    query: str
    results: list[SearchResult]


@router.post("/search", response_model=SearchResponse)
def search_photos(request: SearchRequest) -> SearchResponse:
    """Search indexed photos by natural language query.

    Encodes the query text with CLIP, then performs
    cosine similarity search in Qdrant.
    """
    query_vector = clip_service.encode_text(request.query)
    results = qdrant_service.search(query_vector=query_vector, limit=request.limit)
    return SearchResponse(
        query=request.query,
        results=[SearchResult(**r) for r in results],
    )


@router.get("/photos/{file_path:path}")
def serve_photo(file_path: str) -> Response:
    """Serve a photo file from the photos directory.

    Includes path traversal protection to prevent
    accessing files outside the photos directory.
    """
    photos_root = Path(settings.photos_dir).resolve()
    requested = (photos_root / file_path).resolve()

    # Path traversal protection
    if not requested.is_relative_to(photos_root):
        raise HTTPException(status_code=403, detail="Access denied")

    if not requested.is_file():
        raise HTTPException(status_code=404, detail="Photo not found")

    if clip_service.is_raw_image_path(requested):
        try:
            preview = clip_service.render_preview(requested)
        except Exception as exc:
            logger.exception("Failed to render RAW preview for %s", requested)
            raise HTTPException(
                status_code=500,
                detail="Unable to render RAW photo preview",
            ) from exc
        return Response(content=preview, media_type="image/jpeg")

    media_type, _ = mimetypes.guess_type(requested)
    return FileResponse(
        path=requested,
        media_type=media_type or "application/octet-stream",
    )


class StatusResponse(BaseModel):
    """Response body for the status endpoint."""

    indexed_photos: int
    collection_name: str


@router.get("/status", response_model=StatusResponse)
def get_status() -> StatusResponse:
    """Return current indexing status."""
    count = qdrant_service.get_indexed_count()
    return StatusResponse(
        indexed_photos=count,
        collection_name=settings.collection_name,
    )
