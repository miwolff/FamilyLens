import hashlib
import logging
import uuid

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    PointStruct,
    VectorParams,
)

from app.config import settings

logger = logging.getLogger(__name__)

_client: QdrantClient | None = None


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
            if point.payload and "file_path" in point.payload:
                indexed.add(point.payload["file_path"])
        if next_offset is None:
            break
        offset = next_offset
    return indexed


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
    return [
        {
            "file_path": hit.payload.get("file_path", "") if hit.payload else "",
            "filename": hit.payload.get("filename", "") if hit.payload else "",
            "score": hit.score,
        }
        for hit in results.points
    ]


def get_indexed_count() -> int:
    """Return number of indexed photos."""
    client = get_client()
    info = client.get_collection(settings.collection_name)
    return info.points_count or 0
