from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.routers import index as index_router
from app.services import clustering_service

router = APIRouter()


class ClusterPhoto(BaseModel):
    """A single photo shown in cluster browsing responses."""

    file_path: str
    filename: str
    score: float


class ClusterSummary(BaseModel):
    """Summary information for a single cluster."""

    cluster_id: int
    size: int


class ClusterListResponse(BaseModel):
    """Response body for listing available clusters."""

    status: str
    message: str | None = None
    total_clusters: int = 0
    total_photos: int = 0
    clusters: list[ClusterSummary] = Field(default_factory=list)


class ClusterDetailResponse(BaseModel):
    """Response body for a single cluster page."""

    cluster_id: int
    size: int
    total_clusters: int
    previous_cluster_id: int | None
    next_cluster_id: int | None
    photos: list[ClusterPhoto]


def _photo_model(photo: clustering_service.ClusterPhotoData) -> ClusterPhoto:
    """Convert cluster photo dataclasses into response models."""
    return ClusterPhoto(
        file_path=photo.file_path,
        filename=photo.filename,
        score=photo.score,
    )


def _building_message(stage: str) -> str:
    """Return a user-facing message for cluster rebuild progress."""
    if stage == "clustering":
        return "Clusters are currently being rebuilt."
    return "Clusters will be available after the current indexing run finishes."


@router.get("/clusters", response_model=ClusterListResponse)
def list_clusters() -> ClusterListResponse:
    """List available image clusters for the browse page."""
    progress = index_router.get_progress_snapshot()
    if progress["status"] in {"running", "cancelling"}:
        return ClusterListResponse(
            status="building",
            message=_building_message(progress["stage"]),
        )

    catalog = clustering_service.get_cluster_catalog()
    if catalog.status == "empty":
        return ClusterListResponse(
            status="empty",
            message="Index photos to build clusters.",
            total_clusters=0,
            total_photos=0,
            clusters=[],
        )

    if catalog.status == "unavailable":
        return ClusterListResponse(
            status="unavailable",
            message=(
                progress["cluster_error"]
                or "Run indexing to generate image clusters."
            ),
            total_clusters=0,
            total_photos=catalog.total_photos,
            clusters=[],
        )

    return ClusterListResponse(
        status="ready",
        total_clusters=catalog.total_clusters,
        total_photos=catalog.total_photos,
        clusters=[
            ClusterSummary(
                cluster_id=cluster.cluster_id,
                size=cluster.size,
            )
            for cluster in catalog.clusters
        ],
    )


@router.get("/clusters/{cluster_id}", response_model=ClusterDetailResponse)
def get_cluster(cluster_id: int) -> ClusterDetailResponse:
    """Return one cluster gallery."""
    progress = index_router.get_progress_snapshot()
    if progress["status"] in {"running", "cancelling"}:
        raise HTTPException(
            status_code=409,
            detail=_building_message(progress["stage"]),
        )

    try:
        detail = clustering_service.get_cluster_detail(cluster_id)
    except ValueError:
        raise HTTPException(
            status_code=409,
            detail=(
                progress["cluster_error"]
                or "Run indexing to generate image clusters."
            ),
        ) from None
    except KeyError:
        raise HTTPException(status_code=404, detail="Cluster not found") from None

    return ClusterDetailResponse(
        cluster_id=detail.cluster_id,
        size=detail.size,
        total_clusters=detail.total_clusters,
        previous_cluster_id=detail.previous_cluster_id,
        next_cluster_id=detail.next_cluster_id,
        photos=[_photo_model(photo) for photo in detail.photos],
    )