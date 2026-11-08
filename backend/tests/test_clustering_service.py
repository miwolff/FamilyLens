from types import SimpleNamespace
from unittest.mock import patch

import pytest

from app.services import clustering_service, qdrant_service


def point(
    name: str,
    *,
    vector: list[float] | None = None,
    cluster_id: int | None = None,
    similarity: float | None = None,
) -> qdrant_service.IndexedPoint:
    """Build an IndexedPoint for tests."""
    return qdrant_service.IndexedPoint(
        point_id=name,
        file_path=f"{name}.jpg",
        filename=f"{name}.jpg",
        vector=vector,
        cluster_id=cluster_id,
        cluster_similarity=similarity,
    )


@pytest.fixture
def qdrant():
    """Patch the qdrant_service functions used by the clustering service."""
    target = "app.services.clustering_service.qdrant_service"
    with (
        patch(f"{target}.scroll_indexed_points") as scroll,
        patch(f"{target}.update_cluster_payloads") as update,
        patch(f"{target}.get_indexed_count") as count,
        patch(f"{target}.count_unclustered") as unclustered,
        patch(f"{target}.get_cluster_sizes") as sizes,
    ):
        unclustered.return_value = 0
        yield SimpleNamespace(
            scroll=scroll,
            update=update,
            count=count,
            unclustered=unclustered,
            sizes=sizes,
        )


def test_rebuild_clusters_sorts_cluster_ids_by_size(qdrant):
    """The largest cluster always becomes public cluster 0."""
    qdrant.scroll.return_value = [
        point("a", vector=[1.0, 0.0]),
        point("b", vector=[0.95, 0.05]),
        point("c", vector=[0.9, 0.1]),
        point("d", vector=[0.0, 1.0]),
    ]

    result = clustering_service.rebuild_clusters(cluster_count=2)

    assert result.total_clusters == 2
    updates = qdrant.update.call_args.args[0]
    assert len([u for u in updates if u.cluster_id == 0]) == 3
    assert len([u for u in updates if u.cluster_id == 1]) == 1


def test_rebuild_clusters_empty_index(qdrant):
    """An empty index produces no clusters and writes nothing."""
    qdrant.scroll.return_value = []

    result = clustering_service.rebuild_clusters()

    assert result.total_clusters == 0
    qdrant.update.assert_not_called()


def test_rebuild_clusters_honours_cancellation(qdrant):
    """A cancelled build raises before touching Qdrant."""
    with pytest.raises(clustering_service.ClusteringCancelledError):
        clustering_service.rebuild_clusters(is_cancelled=lambda: True)
    qdrant.scroll.assert_not_called()


def test_catalog_empty_index(qdrant):
    """The catalog reports 'empty' when nothing is indexed."""
    qdrant.count.return_value = 0

    assert clustering_service.get_cluster_catalog().status == "empty"


def test_catalog_unavailable_until_all_points_clustered(qdrant):
    """The catalog is unavailable while some photos lack a cluster id."""
    qdrant.count.return_value = 3
    qdrant.unclustered.return_value = 1

    catalog = clustering_service.get_cluster_catalog()

    assert catalog.status == "unavailable"
    assert catalog.total_photos == 3
    qdrant.sizes.assert_not_called()


def test_catalog_ready_uses_facet_counts_without_scrolling(qdrant):
    """Cluster sizes come from the facet query, not a full scroll."""
    qdrant.count.return_value = 7
    qdrant.sizes.return_value = {1: 2, 0: 5}

    catalog = clustering_service.get_cluster_catalog()

    assert catalog.status == "ready"
    assert catalog.total_clusters == 2
    assert [(c.cluster_id, c.size) for c in catalog.clusters] == [(0, 5), (1, 2)]
    qdrant.scroll.assert_not_called()


def test_cluster_detail_returns_navigation_and_sorted_photos(qdrant):
    """Cluster detail exposes navigation and orders by similarity."""
    qdrant.count.return_value = 3
    qdrant.sizes.return_value = {0: 2, 1: 1}
    qdrant.scroll.return_value = [
        point("b", cluster_id=0, similarity=0.8),
        point("a", cluster_id=0, similarity=0.99),
    ]

    detail = clustering_service.get_cluster_detail(0)

    assert detail.total_clusters == 2
    assert detail.previous_cluster_id is None
    assert detail.next_cluster_id == 1
    assert [p.file_path for p in detail.photos] == ["a.jpg", "b.jpg"]
    qdrant.scroll.assert_called_once_with(with_vectors=False, cluster_id=0)


def test_cluster_detail_unknown_id_raises_key_error(qdrant):
    """Out-of-range cluster ids raise KeyError (mapped to 404)."""
    qdrant.count.return_value = 3
    qdrant.sizes.return_value = {0: 3}

    with pytest.raises(KeyError):
        clustering_service.get_cluster_detail(5)
