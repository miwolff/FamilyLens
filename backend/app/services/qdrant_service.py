import hashlib
import logging
import uuid
from collections.abc import Iterable
from dataclasses import dataclass

from qdrant_client import QdrantClient, models
from qdrant_client.models import (
    Distance,
    PointIdsList,
    PointStruct,
    VectorParams,
)

from app.config import settings

logger = logging.getLogger(__name__)

_client: QdrantClient | None = None


def _get_required_payload_string(
    payload: dict,
    key: str,
    *,
    record_id: str | int,
) -> str:
    """Return a non-empty string payload field or raise ValueError."""
    value = payload.get(key)
    if isinstance(value, str) and value:
        return value
    raise ValueError(f"Record {record_id!s} is missing a valid '{key}' payload field")


@dataclass(slots=True)
class IndexedPoint:
    """Indexed photo record loaded from Qdrant."""

    point_id: str
    file_path: str
    filename: str
    vector: list[float] | None = None
    cluster_id: int | None = None
    cluster_similarity: float | None = None


@dataclass(slots=True)
class ClusterPayloadUpdate:
    """Cluster payload update for a single indexed point."""

    point_id: str
    cluster_id: int
    cluster_similarity: float


def get_client() -> QdrantClient:
    """Return the Qdrant client (singleton)."""
    global _client
    if _client is None:
        _client = QdrantClient(
            host=settings.qdrant_host,
            port=settings.qdrant_port,
        )
        logger.info(
            "Connected to Qdrant at %s:%d",
            settings.qdrant_host,
            settings.qdrant_port,
        )
    return _client


def ensure_collection() -> None:
    """Create the photos collection if it does not exist."""
    client = get_client()
    collections = [c.name for c in client.get_collections().collections]
    if settings.collection_name not in collections:
        client.create_collection(
            collection_name=settings.collection_name,
            vectors_config=VectorParams(
                size=settings.embedding_dim,
                distance=Distance.COSINE,
            ),
        )
        logger.info("Created collection '%s'", settings.collection_name)
    else:
        logger.info(
            "Collection '%s' already exists",
            settings.collection_name,
        )


def file_point_id(file_path: str) -> str:
    """Generate a deterministic UUID from a file path."""
    digest = hashlib.sha256(file_path.encode()).digest()
    return str(uuid.UUID(bytes=digest[:16]))


def _record_to_indexed_point(
    record: models.Record,
    *,
    with_vectors: bool,
) -> IndexedPoint:
    """Convert a Qdrant record into an IndexedPoint."""
    payload = record.payload
    if not payload:
        raise ValueError(f"Record {record.id!s} has no payload")

    raw_vector = record.vector if with_vectors else None
    if isinstance(raw_vector, dict):
        raw_vector = next(iter(raw_vector.values()), None)

    file_path = _get_required_payload_string(
        payload,
        "file_path",
        record_id=record.id,
    )
    filename = _get_required_payload_string(
        payload,
        "filename",
        record_id=record.id,
    )
    cluster_id = payload.get("cluster_id")
    cluster_similarity = payload.get("cluster_similarity")
    return IndexedPoint(
        point_id=str(record.id),
        file_path=file_path,
        filename=filename,
        vector=list(raw_vector) if raw_vector is not None else None,
        cluster_id=int(cluster_id) if cluster_id is not None else None,
        cluster_similarity=(
            float(cluster_similarity) if cluster_similarity is not None else None
        ),
    )


def _chunked(
    items: list[ClusterPayloadUpdate],
    chunk_size: int,
) -> Iterable[list[ClusterPayloadUpdate]]:
    """Yield lists of updates in fixed-size chunks."""
    for start in range(0, len(items), chunk_size):
        yield items[start : start + chunk_size]


def get_indexed_paths() -> set[str]:
    """Return the set of already-indexed file paths."""
    client = get_client()
    indexed: set[str] = set()
    offset = None
    while True:
        results = client.scroll(
            collection_name=settings.collection_name,
            limit=1000,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        points, next_offset = results
        for point in points:
            payload = point.payload or {}
            file_path = payload.get("file_path")
            if isinstance(file_path, str) and file_path:
                indexed.add(file_path)
            elif payload:
                logger.warning(
                    "Skipping malformed indexed path payload for point %s",
                    point.id,
                )
        if next_offset is None:
            break
        offset = next_offset
    return indexed


def scroll_indexed_points(
    *,
    with_vectors: bool = False,
    cluster_id: int | None = None,
) -> list[IndexedPoint]:
    """Scroll indexed points from Qdrant, optionally filtered by cluster."""
    client = get_client()
    points: list[IndexedPoint] = []
    offset = None
    scroll_filter = None

    if cluster_id is not None:
        scroll_filter = models.Filter(
            must=[
                models.FieldCondition(
                    key="cluster_id",
                    match=models.MatchValue(value=cluster_id),
                )
            ]
        )

    while True:
        records, next_offset = client.scroll(
            collection_name=settings.collection_name,
            scroll_filter=scroll_filter,
            limit=256,
            offset=offset,
            with_payload=True,
            with_vectors=with_vectors,
        )
        for record in records:
            try:
                points.append(
                    _record_to_indexed_point(
                        record,
                        with_vectors=with_vectors,
                    )
                )
            except ValueError as exc:
                logger.warning("Skipping malformed record from Qdrant: %s", exc)
        if next_offset is None:
            break
        offset = next_offset

    return points


def update_cluster_payloads(updates: list[ClusterPayloadUpdate]) -> None:
    """Persist cluster metadata for indexed points in batched writes."""
    if not updates:
        return

    client = get_client()
    for batch in _chunked(updates, settings.cluster_payload_batch_size):
        operations = [
            models.SetPayloadOperation(
                set_payload=models.SetPayload(
                    payload={
                        "cluster_id": update.cluster_id,
                        "cluster_similarity": update.cluster_similarity,
                    },
                    points=[update.point_id],
                )
            )
            for update in batch
        ]
        operations.append(
            models.DeletePayloadOperation(
                delete_payload=models.DeletePayload(
                    keys=["cluster_representative_rank"],
                    points=[update.point_id for update in batch],
                )
            )
        )
        client.batch_update_points(
            collection_name=settings.collection_name,
            update_operations=operations,
        )


def upsert_embeddings(
    points: list[tuple[str, str, list[float]]],
) -> None:
    """Batch upsert embeddings with metadata.

    Args:
        points: List of (file_path, filename, embedding) tuples.
    """
    client = get_client()
    qdrant_points = [
        PointStruct(
            id=file_point_id(file_path),
            vector=embedding,
            payload={
                "file_path": file_path,
                "filename": filename,
            },
        )
        for file_path, filename, embedding in points
    ]
    client.upsert(
        collection_name=settings.collection_name,
        points=qdrant_points,
    )


def search(query_vector: list[float], limit: int) -> list[dict]:
    """Search for similar images by query vector.

    Returns list of dicts with file_path, filename, score.
    """
    client = get_client()
    results = client.query_points(
        collection_name=settings.collection_name,
        query=query_vector,
        limit=limit,
        with_payload=True,
    )
    formatted_results: list[dict] = []
    for hit in results.points:
        payload = hit.payload
        if not payload:
            logger.warning(
                "Skipping search result %s with missing payload",
                hit.id,
            )
            continue

        try:
            file_path = _get_required_payload_string(
                payload,
                "file_path",
                record_id=hit.id,
            )
            filename = _get_required_payload_string(
                payload,
                "filename",
                record_id=hit.id,
            )
        except ValueError as exc:
            logger.warning("Skipping malformed search result: %s", exc)
            continue

        formatted_results.append(
            {
                "file_path": file_path,
                "filename": filename,
                "score": hit.score,
            }
        )
    return formatted_results


def check_health() -> bool:
    """Return whether the Qdrant collection is reachable."""
    client = get_client()
    client.get_collection(settings.collection_name)
    return True


def delete_by_paths(paths: list[str]) -> int:
    """Delete indexed entries for the given file paths.

    Returns the number of paths submitted for deletion.
    """
    if not paths:
        return 0
    client = get_client()
    ids = [file_point_id(p) for p in paths]
    client.delete(
        collection_name=settings.collection_name,
        points_selector=PointIdsList(points=[str(id) for id in ids]),
    )
    return len(paths)


def get_indexed_count() -> int:
    """Return number of indexed photos."""
    client = get_client()
    info = client.get_collection(settings.collection_name)
    return info.points_count or 0
