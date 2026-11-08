from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.clustering_service import ClusterBuildResult


def write_photos(root: Path, *relative_paths: str) -> None:
    """Create placeholder image files under root."""
    for relative in relative_paths:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"img")


@pytest.fixture
def pipeline():
    """Mock the CLIP and Qdrant calls made by an indexing run."""
    target = "app.routers.index"
    with (
        patch(f"{target}.clip_service.load_image") as load_image,
        patch(f"{target}.clip_service.encode_images") as encode_images,
        patch(f"{target}.qdrant_service.get_indexed_paths") as indexed_paths,
        patch(f"{target}.qdrant_service.upsert_embeddings") as upsert,
        patch(f"{target}.qdrant_service.delete_by_paths") as delete,
        patch(f"{target}.qdrant_service.get_indexed_count") as count,
        patch(f"{target}.clustering_service.rebuild_clusters") as rebuild,
    ):
        load_image.side_effect = lambda path, max_side=None: MagicMock()
        encode_images.side_effect = lambda images: [[0.1, 0.2] for _ in images]
        indexed_paths.return_value = set()
        delete.side_effect = len
        count.return_value = 0
        rebuild.return_value = ClusterBuildResult(total_clusters=1, total_photos=1)
        yield MagicMock(
            load_image=load_image,
            encode_images=encode_images,
            indexed_paths=indexed_paths,
            upsert=upsert,
            delete=delete,
            rebuild=rebuild,
        )


def run(index_module, folder: Path, **kwargs) -> dict:
    """Run the background indexing worker synchronously."""
    index_module._run_lock.acquire()
    index_module._run_indexing(folder, **kwargs)
    return index_module.get_progress_snapshot()


def upserted_paths(pipeline) -> list[str]:
    """Return every file_path written to Qdrant across all batches."""
    return [
        file_path
        for call in pipeline.upsert.call_args_list
        for file_path, _filename, _vector in call.args[0]
    ]


# --- Endpoint behaviour -----------------------------------------------------


def test_status_returns_idle_initially(api, index_state):
    """GET /api/index/status returns idle when no run has started."""
    response = api.client.get("/api/index/status")

    assert response.status_code == 200
    assert response.json()["status"] == "idle"


def test_index_missing_folder_returns_running_then_error(api, index_state, photos_root):
    """POST returns running immediately; the run then fails on a bad folder."""
    response = api.client.post(
        "/api/index", json={"folder": "missing-folder", "cluster_count": 7}
    )

    assert response.status_code == 200
    assert response.json()["status"] == "running"
    assert response.json()["cluster_count"] == 7
    # TestClient runs background tasks before returning the response.
    assert api.client.get("/api/index/status").json()["status"] == "error"


def test_index_rejects_folder_outside_photos_root(api, index_state, photos_root):
    """Folders outside the configured photos root are rejected."""
    response = api.client.post("/api/index", json={"folder": "../elsewhere"})

    assert response.status_code == 403
    assert "configured photos directory" in response.json()["detail"]


def test_index_returns_409_when_already_running(api, index_state):
    """A second run cannot start while one is in progress."""
    index_state._run_lock.acquire()
    index_state.set_progress_state({"status": "running"})

    response = api.client.post("/api/index", json={})

    assert response.status_code == 409
    assert "already running" in response.json()["detail"].lower()


def test_cancel_when_idle_returns_current_status(api, index_state):
    """Cancelling with nothing running just reports the current status."""
    response = api.client.post("/api/index/cancel")

    assert response.status_code == 200
    assert response.json() == {"status": "idle", "cluster_count": 12}


@pytest.mark.parametrize("cluster_count", [0, 1001])
def test_index_rejects_invalid_cluster_count(api, index_state, cluster_count):
    """Cluster counts outside 1..max_cluster_count are rejected."""
    response = api.client.post("/api/index", json={"cluster_count": cluster_count})

    assert response.status_code == 422


# --- Discovery ---------------------------------------------------------------


def test_discover_images_matches_extensions_case_insensitively(tmp_path):
    """Discovery finds supported formats regardless of extension case."""
    from app.routers.index import _discover_images

    write_photos(
        tmp_path, "photo.jpg", "a/scan.DNG", "negative.nef", "mixed.Jpeg", "x.txt"
    )

    names = {path.name for path in _discover_images(tmp_path)}

    assert names == {"photo.jpg", "scan.DNG", "negative.nef", "mixed.Jpeg"}


# --- Indexing worker ---------------------------------------------------------


def test_run_indexing_completes_with_cluster_result(index_state, photos_root, pipeline):
    """A successful run reports the cluster count and the final result."""
    write_photos(photos_root, "1/photo.jpg")
    pipeline.rebuild.return_value = ClusterBuildResult(total_clusters=4, total_photos=1)

    progress = run(index_state, photos_root, cluster_count=7)

    assert pipeline.rebuild.call_args.kwargs["cluster_count"] == 7
    assert progress["status"] == "complete"
    assert progress["cluster_count"] == 7
    assert progress["result"].indexed == 1
    assert progress["result"].total_clusters == 4
    assert progress["cluster_error"] is None


def test_run_indexing_encodes_in_batches(index_state, photos_root, pipeline):
    """Images are encoded and upserted one batch at a time."""
    write_photos(photos_root, *(f"1/{i}.jpg" for i in range(5)))

    with patch.object(index_state.settings, "index_batch_size", 2):
        progress = run(index_state, photos_root)

    batch_sizes = [len(c.args[0]) for c in pipeline.encode_images.call_args_list]
    assert batch_sizes == [2, 2, 1]
    assert len(upserted_paths(pipeline)) == 5
    assert progress["indexed"] == 5


def test_run_indexing_counts_unreadable_files_and_continues(
    index_state, photos_root, pipeline
):
    """A file that fails to load is counted as an error, not fatal."""
    write_photos(photos_root, "1/good.jpg", "1/broken.jpg")

    def load(path, max_side=None):
        if path.name == "broken.jpg":
            raise OSError("cannot identify image file")
        return MagicMock()

    pipeline.load_image.side_effect = load

    progress = run(index_state, photos_root)

    assert upserted_paths(pipeline) == ["1/good.jpg"]
    assert progress["status"] == "complete"
    assert progress["indexed"] == 1
    assert progress["errors"] == 1


def test_run_indexing_skips_already_indexed(index_state, photos_root, pipeline):
    """Photos already in the index are skipped."""
    write_photos(photos_root, "1/old.jpg", "1/new.jpg")
    pipeline.indexed_paths.return_value = {"1/old.jpg"}

    progress = run(index_state, photos_root)

    assert upserted_paths(pipeline) == ["1/new.jpg"]
    assert progress["skipped"] == 1


def test_run_indexing_cancel_stops_before_clustering(
    index_state, photos_root, pipeline
):
    """A cancelled run stops encoding and never rebuilds clusters."""
    write_photos(photos_root, "1/a.jpg")
    index_state._cancel_event.set()

    progress = run(index_state, photos_root)

    assert progress["status"] == "cancelled"
    pipeline.encode_images.assert_not_called()
    pipeline.rebuild.assert_not_called()


def test_subfolder_run_stores_paths_relative_to_photos_root(
    index_state, photos_root, pipeline
):
    """Regression: indexing a subfolder must keep root-relative paths.

    /api/photos/{file_path} resolves paths against the photos root, so a
    path stored relative to the subfolder could never be served.
    """
    write_photos(photos_root, "1/trips/beach.jpg")

    run(index_state, photos_root / "1" / "trips")

    assert upserted_paths(pipeline) == ["1/trips/beach.jpg"]


def test_subfolder_cleanup_only_removes_stale_entries_in_that_folder(
    index_state, photos_root, pipeline
):
    """Regression: cleanup of a subfolder must not wipe other folders."""
    write_photos(photos_root, "1/trips/kept.jpg", "2/other.jpg")
    pipeline.indexed_paths.return_value = {
        "1/trips/kept.jpg",
        "1/trips/deleted.jpg",
        "1/trips-2024/unrelated.jpg",
        "2/other.jpg",
    }

    progress = run(index_state, photos_root / "1" / "trips", cleanup=True)

    pipeline.delete.assert_called_once_with(["1/trips/deleted.jpg"])
    assert progress["removed"] == 1
    assert progress["skipped"] == 1


def test_root_cleanup_removes_all_stale_entries(index_state, photos_root, pipeline):
    """Cleanup from the root removes every entry missing on disk."""
    write_photos(photos_root, "1/kept.jpg")
    pipeline.indexed_paths.return_value = {"1/kept.jpg", "1/gone.jpg", "2/gone.jpg"}

    run(index_state, photos_root, cleanup=True)

    assert sorted(pipeline.delete.call_args.args[0]) == ["1/gone.jpg", "2/gone.jpg"]
