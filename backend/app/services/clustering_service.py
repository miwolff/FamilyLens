import logging
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from app.config import settings
from app.services import qdrant_service

logger = logging.getLogger(__name__)


class ClusteringCancelledError(RuntimeError):
    """Raised when a cluster build is cancelled."""


@dataclass(slots=True)
class ClusterPhotoData:
    """Photo metadata exposed by cluster APIs."""

    file_path: str
    filename: str
    score: float


@dataclass(slots=True)
class ClusterSummaryData:
    """Summary metadata for a single cluster."""

    cluster_id: int
    size: int


@dataclass(slots=True)
class ClusterCatalogData:
    """Cluster catalog returned to the browse UI."""

    status: str
    total_clusters: int
    total_photos: int
    clusters: list[ClusterSummaryData]


@dataclass(slots=True)
class ClusterDetailData:
    """Full details for a single cluster."""

    cluster_id: int
    size: int
    total_clusters: int
    previous_cluster_id: int | None
    next_cluster_id: int | None
    photos: list[ClusterPhotoData]


@dataclass(slots=True)
class ClusterBuildResult:
    """Result of rebuilding cluster assignments."""

    total_clusters: int
    total_photos: int


def _raise_if_cancelled(
    is_cancelled: Callable[[], bool] | None,
) -> None:
    """Stop processing if cancellation was requested."""
    if is_cancelled and is_cancelled():
        raise ClusteringCancelledError("Clustering cancelled")


def _normalize_rows(vectors: np.ndarray) -> np.ndarray:
    """Normalize vectors row-wise for cosine similarity."""
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms = np.clip(norms, 1e-12, None)
    return vectors / norms


def _build_kmeans(
    n_clusters: int,
    batch_size: int,
):
    """Create the MiniBatchKMeans instance lazily."""
    from sklearn.cluster import MiniBatchKMeans

    return MiniBatchKMeans(
        n_clusters=n_clusters,
        batch_size=batch_size,
        n_init="auto",
        random_state=settings.cluster_random_seed,
    )


def _to_photo(point: qdrant_service.IndexedPoint) -> ClusterPhotoData:
    """Convert an indexed point into a cluster photo response shape."""
    return ClusterPhotoData(
        file_path=point.file_path,
        filename=point.filename,
        score=point.cluster_similarity or 0.0,
    )


def _sort_cluster_members(
    points: list[qdrant_service.IndexedPoint],
) -> list[qdrant_service.IndexedPoint]:
    """Sort cluster members by similarity so the strongest matches come first."""
    return sorted(
        points,
        key=lambda point: (
            -(point.cluster_similarity or 0.0),
            point.file_path,
        ),
    )


def rebuild_clusters(
    is_cancelled: Callable[[], bool] | None = None,
) -> ClusterBuildResult:
    """Recompute cluster membership for all photos."""
    _raise_if_cancelled(is_cancelled)
    indexed_points = qdrant_service.scroll_indexed_points(with_vectors=True)
    total_photos = len(indexed_points)

    if total_photos == 0:
        logger.info("Skipping cluster rebuild because the index is empty")
        return ClusterBuildResult(total_clusters=0, total_photos=0)

    vectors = np.asarray(
        [point.vector for point in indexed_points],
        dtype=np.float32,
    )
    _raise_if_cancelled(is_cancelled)

    n_clusters = min(settings.cluster_count, total_photos)
    if total_photos == 1 or n_clusters == 1:
        labels = np.zeros(total_photos, dtype=np.int32)
        centers = vectors[:1]
    else:
        batch_size = min(max(n_clusters * 16, 256), total_photos)
        model = _build_kmeans(n_clusters=n_clusters, batch_size=batch_size)
        labels = model.fit_predict(vectors)
        centers = model.cluster_centers_

    normalized_centers = _normalize_rows(np.asarray(centers, dtype=np.float32))
    similarities = np.sum(vectors * normalized_centers[labels], axis=1)

    members_by_label: dict[int, list[int]] = defaultdict(list)
    for index, label in enumerate(labels.tolist()):
        members_by_label[label].append(index)

    sorted_labels = sorted(
        members_by_label,
        key=lambda label: (
            -len(members_by_label[label]),
            -float(np.mean(similarities[members_by_label[label]])),
            label,
        ),
    )

    updates: list[qdrant_service.ClusterPayloadUpdate] = []
    for public_cluster_id, label in enumerate(sorted_labels):
        member_indices = members_by_label[label]

        for idx in member_indices:
            updates.append(
                qdrant_service.ClusterPayloadUpdate(
                    point_id=indexed_points[idx].point_id,
                    cluster_id=public_cluster_id,
                    cluster_similarity=float(similarities[idx]),
                )
            )

    _raise_if_cancelled(is_cancelled)
    qdrant_service.update_cluster_payloads(updates)
    logger.info(
        "Rebuilt %d clusters across %d photos",
        len(sorted_labels),
        total_photos,
    )
    return ClusterBuildResult(
        total_clusters=len(sorted_labels),
        total_photos=total_photos,
    )


def get_cluster_catalog() -> ClusterCatalogData:
    """Return cluster summaries for the browse UI."""
    indexed_points = qdrant_service.scroll_indexed_points(with_vectors=False)
    total_photos = len(indexed_points)
    if total_photos == 0:
        return ClusterCatalogData(
            status="empty",
            total_clusters=0,
            total_photos=0,
            clusters=[],
        )

    if any(point.cluster_id is None for point in indexed_points):
        return ClusterCatalogData(
            status="unavailable",
            total_clusters=0,
            total_photos=total_photos,
            clusters=[],
        )

    clusters: dict[int, list[qdrant_service.IndexedPoint]] = defaultdict(list)
    for point in indexed_points:
        clusters[point.cluster_id or 0].append(point)

    summaries: list[ClusterSummaryData] = []
    for cluster_id in sorted(clusters):
        members = _sort_cluster_members(clusters[cluster_id])
        summaries.append(
            ClusterSummaryData(
                cluster_id=cluster_id,
                size=len(members),
            )
        )

    return ClusterCatalogData(
        status="ready",
        total_clusters=len(summaries),
        total_photos=total_photos,
        clusters=summaries,
    )


def get_cluster_detail(cluster_id: int) -> ClusterDetailData:
    """Return one cluster with the full gallery."""
    catalog = get_cluster_catalog()
    if catalog.status != "ready":
        raise ValueError(catalog.status)

    if cluster_id < 0 or cluster_id >= catalog.total_clusters:
        raise KeyError(cluster_id)

    members = _sort_cluster_members(
        qdrant_service.scroll_indexed_points(
            with_vectors=False,
            cluster_id=cluster_id,
        )
    )
    if not members:
        raise KeyError(cluster_id)

    return ClusterDetailData(
        cluster_id=cluster_id,
        size=len(members),
        total_clusters=catalog.total_clusters,
        previous_cluster_id=cluster_id - 1 if cluster_id > 0 else None,
        next_cluster_id=(
            cluster_id + 1
            if cluster_id + 1 < catalog.total_clusters
            else None
        ),
        photos=[_to_photo(point) for point in members],
    )