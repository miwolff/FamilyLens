from unittest.mock import patch

from app.services import clustering_service


def idle_progress(**overrides) -> dict:
    """Return an indexing progress snapshot with no run in progress."""
    return {"status": "idle", "stage": "idle", "cluster_error": None, **overrides}


def test_list_clusters_returns_ready_catalog(api):
    """GET /api/clusters returns the catalog when clusters are ready."""
    catalog = clustering_service.ClusterCatalogData(
        status="ready",
        total_clusters=1,
        total_photos=3,
        clusters=[clustering_service.ClusterSummaryData(cluster_id=0, size=3)],
    )
    with (
        patch("app.routers.index.get_progress_snapshot", return_value=idle_progress()),
        patch(
            "app.services.clustering_service.get_cluster_catalog",
            return_value=catalog,
        ),
    ):
        response = api.client.get("/api/clusters")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ready"
    assert data["total_clusters"] == 1
    assert data["clusters"] == [{"cluster_id": 0, "size": 3}]


def test_list_clusters_reports_building_during_indexing(api):
    """GET /api/clusters reports 'building' while an indexing run is active."""
    progress = idle_progress(status="running", stage="indexing")
    with patch("app.routers.index.get_progress_snapshot", return_value=progress):
        response = api.client.get("/api/clusters")

    assert response.json()["status"] == "building"


def test_get_cluster_returns_409_while_building(api):
    """GET /api/clusters/<id> is unavailable during cluster rebuilds."""
    progress = idle_progress(status="running", stage="clustering")
    with patch("app.routers.index.get_progress_snapshot", return_value=progress):
        response = api.client.get("/api/clusters/0")

    assert response.status_code == 409
    assert "rebuilt" in response.json()["detail"].lower()


def test_get_cluster_returns_404_for_unknown_id(api):
    """GET /api/clusters/<id> returns 404 for a cluster that does not exist."""
    with (
        patch("app.routers.index.get_progress_snapshot", return_value=idle_progress()),
        patch(
            "app.services.clustering_service.get_cluster_detail",
            side_effect=KeyError(9),
        ),
    ):
        response = api.client.get("/api/clusters/9")

    assert response.status_code == 404
