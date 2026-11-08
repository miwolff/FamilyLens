import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.services import qdrant_service


@pytest.fixture
def client():
    """Patch the Qdrant client singleton with a mock."""
    with patch.object(qdrant_service, "get_client") as get_client:
        yield get_client.return_value


def test_file_point_id_is_deterministic_uuid():
    """file_point_id returns the same valid UUID for the same path."""
    first = qdrant_service.file_point_id("photos/beach.jpg")

    assert first == qdrant_service.file_point_id("photos/beach.jpg")
    assert first != qdrant_service.file_point_id("photos/mountain.jpg")
    uuid.UUID(first)


def test_ensure_collection_creates_new(client):
    """The collection is created when it does not exist yet."""
    client.get_collections.return_value.collections = []

    qdrant_service.ensure_collection()

    client.create_collection.assert_called_once()


def test_ensure_collection_already_exists(client):
    """An existing collection is reused."""
    existing = MagicMock()
    existing.name = "photos"
    client.get_collections.return_value.collections = [existing]

    qdrant_service.ensure_collection()

    client.create_collection.assert_not_called()


def test_ensure_collection_indexes_cluster_id(client):
    """cluster_id gets an integer payload index for facets and filters."""
    client.get_collections.return_value.collections = []

    qdrant_service.ensure_collection()

    kwargs = client.create_payload_index.call_args.kwargs
    assert kwargs["field_name"] == "cluster_id"
    assert kwargs["field_schema"] == qdrant_service.models.PayloadSchemaType.INTEGER


def test_delete_by_paths_calls_delete(client):
    """delete_by_paths deletes the point IDs derived from the paths."""
    paths = ["vacation/beach.jpg", "family/reunion.jpg"]

    assert qdrant_service.delete_by_paths(paths) == 2

    kwargs = client.delete.call_args.kwargs
    assert kwargs["collection_name"] == "photos"
    assert set(kwargs["points_selector"].points) == {
        qdrant_service.file_point_id(p) for p in paths
    }


def test_delete_by_paths_empty_list(client):
    """delete_by_paths returns 0 and skips the delete call for no paths."""
    assert qdrant_service.delete_by_paths([]) == 0
    client.delete.assert_not_called()


def test_search_returns_formatted_results(client):
    """search returns dicts with file_path, filename and score."""
    hit = MagicMock(score=0.85)
    hit.payload = {"file_path": "beach.jpg", "filename": "beach.jpg"}
    client.query_points.return_value.points = [hit]

    results = qdrant_service.search([0.1] * 512, limit=10)

    assert results == [
        {"file_path": "beach.jpg", "filename": "beach.jpg", "score": 0.85}
    ]


def test_search_skips_malformed_payloads(client):
    """search skips results whose payloads lack required fields."""
    invalid = MagicMock(id="bad", score=0.11)
    invalid.payload = {"filename": "missing-path.jpg"}
    valid = MagicMock(id="good", score=0.91)
    valid.payload = {"file_path": "albums/beach.jpg", "filename": "beach.jpg"}
    client.query_points.return_value.points = [invalid, valid]

    results = qdrant_service.search([0.1] * 512, limit=10)

    assert results == [
        {"file_path": "albums/beach.jpg", "filename": "beach.jpg", "score": 0.91}
    ]


def test_get_indexed_paths_paginates(client):
    """get_indexed_paths scrolls until next_offset is None."""

    def point(path: str) -> MagicMock:
        return MagicMock(payload={"file_path": path})

    client.scroll.side_effect = [
        ([point("a.jpg"), point("b.jpg")], "page2"),
        ([point("c.jpg")], None),
    ]

    assert qdrant_service.get_indexed_paths() == {"a.jpg", "b.jpg", "c.jpg"}
    assert client.scroll.call_count == 2


def test_get_cluster_sizes_reads_facet_counts(client):
    """get_cluster_sizes maps facet hits to {cluster_id: size}."""
    client.facet.return_value.hits = [
        MagicMock(value=0, count=5),
        MagicMock(value=1, count=2),
    ]

    assert qdrant_service.get_cluster_sizes() == {0: 5, 1: 2}
    assert client.facet.call_args.kwargs["key"] == "cluster_id"
    assert client.facet.call_args.kwargs["exact"] is True


def test_count_unclustered_filters_on_missing_cluster_id(client):
    """count_unclustered counts points whose cluster_id is empty."""
    client.count.return_value.count = 3

    assert qdrant_service.count_unclustered() == 3

    condition = client.count.call_args.kwargs["count_filter"].must[0]
    assert condition.is_empty.key == "cluster_id"
