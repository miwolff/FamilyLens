import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestClipService:
    """Tests for the CLIP service module."""

    @patch("app.services.clip_service.SentenceTransformer")
    def test_load_model(self, mock_st_class):
        """Model loads successfully and is cached."""
        from app.services import clip_service

        clip_service._model = None
        mock_model = MagicMock()
        mock_st_class.return_value = mock_model

        result = clip_service.load_model()
        assert result is mock_model
        mock_st_class.assert_called_once_with("clip-ViT-B-32")

        # Second call returns cached model
        result2 = clip_service.load_model()
        assert result2 is mock_model
        assert mock_st_class.call_count == 1

        clip_service._model = None

    def test_get_model_not_loaded_raises(self):
        """get_model raises RuntimeError if model not loaded."""
        from app.services import clip_service

        clip_service._model = None
        with pytest.raises(RuntimeError, match="not loaded"):
            clip_service.get_model()

    @patch("app.services.clip_service.SentenceTransformer")
    def test_encode_text(self, mock_st_class):
        """encode_text returns a list of floats."""
        import numpy as np
        from app.services import clip_service

        clip_service._model = None
        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.randn(512)
        mock_st_class.return_value = mock_model

        clip_service.load_model()
        result = clip_service.encode_text("sunset on the beach")

        assert isinstance(result, list)
        assert len(result) == 512
        mock_model.encode.assert_called_once_with(
            "sunset on the beach", normalize_embeddings=True
        )

        clip_service._model = None

    @patch("app.services.clip_service.Image")
    @patch("app.services.clip_service.SentenceTransformer")
    def test_encode_image(self, mock_st_class, mock_pil):
        """encode_image opens image, converts to RGB, encodes."""
        import numpy as np
        from app.services import clip_service

        clip_service._model = None
        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.randn(512)
        mock_st_class.return_value = mock_model

        mock_img = MagicMock()
        mock_pil.open.return_value.__enter__.return_value.convert.return_value = (
            mock_img
        )

        clip_service.load_model()
        result = clip_service.encode_image(Path("/test/photo.jpg"))

        assert isinstance(result, list)
        assert len(result) == 512
        mock_pil.open.assert_called_once_with(Path("/test/photo.jpg"))
        mock_pil.open.return_value.__enter__.return_value.convert.assert_called_once_with(
            "RGB"
        )
        mock_model.encode.assert_called_once_with(mock_img, normalize_embeddings=True)
        mock_img.close.assert_called_once_with()

        clip_service._model = None

    @patch("app.services.clip_service.rawpy")
    @patch("app.services.clip_service.Image")
    @patch("app.services.clip_service.SentenceTransformer")
    def test_encode_raw_image(self, mock_st_class, mock_image, mock_rawpy):
        """encode_image decodes RAW images before encoding."""
        import numpy as np
        from app.services import clip_service

        clip_service._model = None
        mock_model = MagicMock()
        mock_model.encode.return_value = np.random.randn(512)
        mock_st_class.return_value = mock_model

        mock_img = MagicMock()
        mock_image.fromarray.return_value.convert.return_value = mock_img
        mock_raw = MagicMock()
        mock_raw.postprocess.return_value = "rgb-data"
        mock_rawpy.imread.return_value.__enter__.return_value = mock_raw

        clip_service.load_model()
        result = clip_service.encode_image(Path("/test/photo.dng"))

        assert isinstance(result, list)
        assert len(result) == 512
        mock_rawpy.imread.assert_called_once_with("/test/photo.dng")
        mock_raw.postprocess.assert_called_once_with()
        mock_image.fromarray.assert_called_once_with("rgb-data")
        mock_image.fromarray.return_value.convert.assert_called_once_with("RGB")
        mock_model.encode.assert_called_once_with(mock_img, normalize_embeddings=True)
        mock_img.close.assert_called_once_with()

        clip_service._model = None


class TestQdrantService:
    """Tests for the Qdrant service module."""

    def test_file_point_id_deterministic(self):
        """file_point_id returns consistent UUID for same path."""
        from app.services.qdrant_service import file_point_id

        id1 = file_point_id("photos/beach.jpg")
        id2 = file_point_id("photos/beach.jpg")
        assert id1 == id2
        # Must be a valid UUID string
        uuid.UUID(id1)

    def test_file_point_id_different_paths(self):
        """Different paths produce different IDs."""
        from app.services.qdrant_service import file_point_id

        id1 = file_point_id("photos/beach.jpg")
        id2 = file_point_id("photos/mountain.jpg")
        assert id1 != id2

    @patch("app.services.qdrant_service.get_client")
    def test_ensure_collection_creates_new(self, mock_get):
        """Creates collection when it doesn't exist."""
        from app.services.qdrant_service import ensure_collection

        mock_client = MagicMock()
        mock_client.get_collections.return_value.collections = []
        mock_get.return_value = mock_client

        ensure_collection()
        mock_client.create_collection.assert_called_once()

    @patch("app.services.qdrant_service.get_client")
    def test_ensure_collection_already_exists(self, mock_get):
        """Skips creation when collection exists."""
        from app.services.qdrant_service import ensure_collection

        mock_client = MagicMock()
        mock_coll = MagicMock()
        mock_coll.name = "photos"
        mock_client.get_collections.return_value.collections = [mock_coll]
        mock_get.return_value = mock_client

        ensure_collection()
        mock_client.create_collection.assert_not_called()

    @patch("app.services.qdrant_service.get_client")
    def test_delete_by_paths_calls_delete(self, mock_get):
        """delete_by_paths calls client.delete with correct point IDs."""
        from app.services.qdrant_service import delete_by_paths, file_point_id

        mock_client = MagicMock()
        mock_get.return_value = mock_client

        paths = ["vacation/beach.jpg", "family/reunion.jpg"]
        result = delete_by_paths(paths)

        assert result == 2
        mock_client.delete.assert_called_once()
        call_kwargs = mock_client.delete.call_args
        assert call_kwargs.kwargs["collection_name"] == "photos"
        submitted_ids = call_kwargs.kwargs["points_selector"].points
        assert set(submitted_ids) == {file_point_id(p) for p in paths}

    @patch("app.services.qdrant_service.get_client")
    def test_delete_by_paths_empty_list(self, mock_get):
        """delete_by_paths returns 0 and skips delete call for empty input."""
        from app.services.qdrant_service import delete_by_paths

        mock_client = MagicMock()
        mock_get.return_value = mock_client

        result = delete_by_paths([])

        assert result == 0
        mock_client.delete.assert_not_called()

    @patch("app.services.qdrant_service.get_client")
    def test_search_returns_formatted_results(self, mock_get):
        """search returns list of dicts with expected keys."""
        from app.services.qdrant_service import search

        mock_client = MagicMock()
        mock_hit = MagicMock()
        mock_hit.payload = {
            "file_path": "beach.jpg",
            "filename": "beach.jpg",
        }
        mock_hit.score = 0.85
        mock_client.query_points.return_value.points = [mock_hit]
        mock_get.return_value = mock_client

        results = search([0.1] * 512, limit=10)
        assert len(results) == 1
        assert results[0]["file_path"] == "beach.jpg"
        assert results[0]["score"] == 0.85


class TestSearchRouter:
    """Tests for the search API endpoint."""

    @patch("app.services.clip_service._model", new=MagicMock())
    @patch("app.services.qdrant_service.get_client")
    @patch("app.services.clip_service.get_model")
    def test_serve_photo_path_traversal(self, mock_get_model, mock_get_client):
        """Path traversal attempts are blocked."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/photos/../../etc/passwd")
        assert response.status_code in (403, 404)


class TestIndexRouter:
    """Tests for the index API endpoint."""

    def setup_method(self):
        """Reset index router state before each test."""
        from app.routers import index as index_module

        if index_module._run_lock.locked():
            index_module._run_lock.release()
        index_module._cancel_event.clear()
        index_module._progress.update(
            {
                "status": "idle",
                "stage": "idle",
                "current": 0,
                "total": 0,
                "indexed": 0,
                "skipped": 0,
                "errors": 0,
                "removed": 0,
                "started_at": 0.0,
                "elapsed_seconds": 0.0,
                "eta_seconds": None,
                "cluster_error": None,
                "result": None,
            }
        )

    @patch("app.services.clip_service._model", new=MagicMock())
    @patch("app.services.qdrant_service.get_client")
    @patch("app.services.clip_service.get_model")
    def test_status_returns_idle_initially(self, mock_get_model, mock_get_client):
        """GET /api/index/status returns idle when no run has started."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/api/index/status")
        assert response.status_code == 200
        assert response.json()["status"] == "idle"

    @patch("app.services.clip_service._model", new=MagicMock())
    @patch("app.services.qdrant_service.get_client")
    @patch("app.services.clip_service.get_model")
    def test_index_missing_folder_returns_running_then_error(
        self, mock_get_model, mock_get_client
    ):
        """POST returns running immediately; status shows error after bg task."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/api/index",
            json={"folder": "/nonexistent/folder"},
        )
        assert response.status_code == 200
        assert response.json()["status"] == "running"

        # Background task runs synchronously in TestClient before returning,
        # so status is already updated by the time we poll.
        status_response = client.get("/api/index/status")
        assert status_response.json()["status"] == "error"

    @patch("app.services.clip_service._model", new=MagicMock())
    @patch("app.services.qdrant_service.get_client")
    @patch("app.services.clip_service.get_model")
    def test_index_returns_409_when_already_running(
        self, mock_get_model, mock_get_client
    ):
        """POST /api/index returns 409 when indexing is already in progress."""
        from app.main import app
        from app.routers import index as index_module
        from fastapi.testclient import TestClient

        index_module._run_lock.acquire()
        index_module._progress["status"] = "running"
        try:
            client = TestClient(app)
            response = client.post("/api/index", json={})
            assert response.status_code == 409
            assert "already running" in response.json()["detail"].lower()
        finally:
            index_module._run_lock.release()
            index_module._progress["status"] = "idle"

    @patch("app.services.clip_service._model", new=MagicMock())
    @patch("app.services.qdrant_service.get_client")
    @patch("app.services.clip_service.get_model")
    def test_cancel_when_idle_returns_current_status(
        self, mock_get_model, mock_get_client
    ):
        """POST /api/index/cancel when idle returns the current status."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.post("/api/index/cancel")
        assert response.status_code == 200
        assert response.json()["status"] == "idle"

    def test_discover_images_includes_raw_formats(self):
        """_discover_images finds DNG and NEF files alongside standard images."""
        import tempfile

        from app.routers.index import _discover_images

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            for name in ["photo.jpg", "scan.DNG", "negative.nef", "note.txt"]:
                (root / name).write_bytes(b"test")

            results = _discover_images(root)

        assert {path.name for path in results} == {
            "photo.jpg",
            "scan.DNG",
            "negative.nef",
        }


class TestSearchRouterFull:
    """Additional tests for the search and photo-serving endpoints."""

    @patch("app.services.clip_service._model", new=MagicMock())
    @patch("app.services.qdrant_service.get_client")
    @patch("app.services.clip_service.get_model")
    def test_search_returns_results(self, mock_get_model, mock_get_client):
        """POST /api/search returns formatted results."""
        import numpy as np
        from app.main import app
        from fastapi.testclient import TestClient

        mock_model = MagicMock()
        mock_model.encode.return_value = np.zeros(512)
        mock_get_model.return_value = mock_model

        mock_hit = MagicMock()
        mock_hit.payload = {"file_path": "beach.jpg", "filename": "beach.jpg"}
        mock_hit.score = 0.9
        mock_client = MagicMock()
        mock_client.query_points.return_value.points = [mock_hit]
        mock_get_client.return_value = mock_client

        client = TestClient(app)
        response = client.post("/api/search", json={"query": "beach sunset"})
        assert response.status_code == 200
        data = response.json()
        assert data["query"] == "beach sunset"
        assert len(data["results"]) == 1
        assert data["results"][0]["file_path"] == "beach.jpg"
        assert data["results"][0]["score"] == 0.9

    @patch("app.services.clip_service._model", new=MagicMock())
    @patch("app.services.qdrant_service.get_client")
    @patch("app.services.clip_service.get_model")
    def test_search_empty_query_rejected(self, mock_get_model, mock_get_client):
        """POST /api/search rejects an empty query string."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.post("/api/search", json={"query": ""})
        assert response.status_code == 422

    @patch("app.services.clip_service._model", new=MagicMock())
    @patch("app.services.qdrant_service.get_client")
    @patch("app.services.clip_service.get_model")
    def test_search_query_too_long_rejected(self, mock_get_model, mock_get_client):
        """POST /api/search rejects queries exceeding 500 characters."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.post("/api/search", json={"query": "x" * 501})
        assert response.status_code == 422

    @patch("app.services.clip_service._model", new=MagicMock())
    @patch("app.services.qdrant_service.get_client")
    @patch("app.services.clip_service.get_model")
    def test_serve_photo_jpeg_content_type(self, mock_get_model, mock_get_client):
        """GET /api/photos/<path> returns image/jpeg for .jpg files."""
        import os
        import tempfile
        from unittest.mock import patch as mock_patch

        from app.main import app
        from fastapi.testclient import TestClient

        tmpdir = tempfile.mkdtemp()
        tmp_file = os.path.join(tmpdir, "test.jpg")
        try:
            with open(tmp_file, "wb") as f:
                f.write(b"\xff\xd8\xff" + b"\x00" * 10)
            with mock_patch("app.routers.search.settings") as mock_settings:
                mock_settings.photos_dir = tmpdir
                client = TestClient(app)
                response = client.get("/api/photos/test.jpg")
            assert response.status_code == 200
            assert "image/jpeg" in response.headers["content-type"]
        finally:
            os.unlink(tmp_file)
            os.rmdir(tmpdir)

    @patch("app.services.clip_service._model", new=MagicMock())
    @patch("app.services.qdrant_service.get_client")
    @patch("app.services.clip_service.get_model")
    def test_serve_photo_png_content_type(self, mock_get_model, mock_get_client):
        """GET /api/photos/<path> returns image/png for .png files."""
        import os
        import tempfile
        from unittest.mock import patch as mock_patch

        from app.main import app
        from fastapi.testclient import TestClient

        tmpdir = tempfile.mkdtemp()
        tmp_file = os.path.join(tmpdir, "test.png")
        try:
            with open(tmp_file, "wb") as f:
                f.write(b"\x89PNG\r\n\x1a\n" + b"\x00" * 10)
            with mock_patch("app.routers.search.settings") as mock_settings:
                mock_settings.photos_dir = tmpdir
                client = TestClient(app)
                response = client.get("/api/photos/test.png")
            assert response.status_code == 200
            assert "image/png" in response.headers["content-type"]
        finally:
            os.unlink(tmp_file)
            os.rmdir(tmpdir)

    @patch("app.services.clip_service.render_preview")
    @patch("app.services.clip_service._model", new=MagicMock())
    @patch("app.services.qdrant_service.get_client")
    @patch("app.services.clip_service.get_model")
    def test_serve_photo_raw_preview_content_type(
        self,
        mock_get_model,
        mock_get_client,
        mock_render_preview,
    ):
        """GET /api/photos/<path> returns a JPEG preview for RAW files."""
        import os
        import tempfile
        from unittest.mock import patch as mock_patch

        from app.main import app
        from fastapi.testclient import TestClient

        mock_render_preview.return_value = b"jpeg-preview"

        tmpdir = tempfile.mkdtemp()
        tmp_file = os.path.join(tmpdir, "test.nef")
        try:
            with open(tmp_file, "wb") as f:
                f.write(b"RAWDATA")
            with mock_patch("app.routers.search.settings") as mock_settings:
                mock_settings.photos_dir = tmpdir
                client = TestClient(app)
                response = client.get("/api/photos/test.nef")
            assert response.status_code == 200
            assert response.content == b"jpeg-preview"
            assert "image/jpeg" in response.headers["content-type"]
            mock_render_preview.assert_called_once_with(Path(tmp_file).resolve())
        finally:
            os.unlink(tmp_file)
            os.rmdir(tmpdir)

    @patch("app.services.clip_service._model", new=MagicMock())
    @patch("app.services.qdrant_service.get_client")
    @patch("app.services.clip_service.get_model")
    def test_serve_photo_not_found(self, mock_get_model, mock_get_client):
        """GET /api/photos/<path> returns 404 for a nonexistent file."""
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)
        response = client.get("/api/photos/nonexistent_file_xyz.jpg")
        assert response.status_code == 404


class TestQdrantServicePagination:
    """Tests for Qdrant service pagination logic."""

    @patch("app.services.qdrant_service.get_client")
    def test_get_indexed_paths_paginates(self, mock_get):
        """get_indexed_paths scrolls through all pages until next_offset is None."""
        from app.services.qdrant_service import get_indexed_paths

        mock_client = MagicMock()
        mock_get.return_value = mock_client

        def make_point(path: str) -> MagicMock:
            p = MagicMock()
            p.payload = {"file_path": path}
            return p

        # Two pages: first returns offset "page2", second returns None
        page1_points = [make_point("a.jpg"), make_point("b.jpg")]
        page2_points = [make_point("c.jpg")]
        mock_client.scroll.side_effect = [
            (page1_points, "page2"),
            (page2_points, None),
        ]

        result = get_indexed_paths()
        assert result == {"a.jpg", "b.jpg", "c.jpg"}
        assert mock_client.scroll.call_count == 2


class TestClusteringService:
    """Tests for the clustering service."""

    @patch("app.services.clustering_service.qdrant_service.update_cluster_payloads")
    @patch("app.services.clustering_service.qdrant_service.scroll_indexed_points")
    def test_rebuild_clusters_sorts_cluster_ids_by_size(
        self,
        mock_scroll,
        mock_update,
    ):
        """Largest cluster should always become public cluster 0."""
        from app.services import clustering_service, qdrant_service

        mock_scroll.return_value = [
            qdrant_service.IndexedPoint(
                point_id="a",
                file_path="a.jpg",
                filename="a.jpg",
                vector=[1.0, 0.0],
            ),
            qdrant_service.IndexedPoint(
                point_id="b",
                file_path="b.jpg",
                filename="b.jpg",
                vector=[0.95, 0.05],
            ),
            qdrant_service.IndexedPoint(
                point_id="c",
                file_path="c.jpg",
                filename="c.jpg",
                vector=[0.9, 0.1],
            ),
            qdrant_service.IndexedPoint(
                point_id="d",
                file_path="d.jpg",
                filename="d.jpg",
                vector=[0.0, 1.0],
            ),
        ]

        with patch.object(clustering_service.settings, "cluster_count", 2), patch.object(
            clustering_service.settings,
            "cluster_representative_count",
            2,
        ):
            result = clustering_service.rebuild_clusters()

        assert result.total_clusters == 2
        updates = mock_update.call_args.args[0]
        cluster_zero_updates = [u for u in updates if u.cluster_id == 0]
        cluster_one_updates = [u for u in updates if u.cluster_id == 1]
        assert len(cluster_zero_updates) == 3
        assert len(cluster_one_updates) == 1
        assert sum(u.cluster_representative_rank is not None for u in updates) == 3

    @patch("app.services.clustering_service.qdrant_service.scroll_indexed_points")
    def test_get_cluster_catalog_reports_unavailable_without_payloads(
        self,
        mock_scroll,
    ):
        """Cluster browse data is unavailable until cluster ids are stored."""
        from app.services import clustering_service, qdrant_service

        mock_scroll.return_value = [
            qdrant_service.IndexedPoint(
                point_id="a",
                file_path="a.jpg",
                filename="a.jpg",
            )
        ]

        catalog = clustering_service.get_cluster_catalog()

        assert catalog.status == "unavailable"
        assert catalog.total_photos == 1

    @patch("app.services.clustering_service.qdrant_service.scroll_indexed_points")
    def test_get_cluster_detail_returns_navigation_and_sorted_photos(
        self,
        mock_scroll,
    ):
        """Cluster detail exposes navigation and representative-first ordering."""
        from app.services import clustering_service, qdrant_service

        all_points = [
            qdrant_service.IndexedPoint(
                point_id="a",
                file_path="a.jpg",
                filename="a.jpg",
                cluster_id=0,
                cluster_similarity=0.99,
                cluster_representative_rank=1,
            ),
            qdrant_service.IndexedPoint(
                point_id="b",
                file_path="b.jpg",
                filename="b.jpg",
                cluster_id=0,
                cluster_similarity=0.8,
                cluster_representative_rank=None,
            ),
            qdrant_service.IndexedPoint(
                point_id="c",
                file_path="c.jpg",
                filename="c.jpg",
                cluster_id=1,
                cluster_similarity=0.95,
                cluster_representative_rank=1,
            ),
        ]
        cluster_zero_points = all_points[:2]
        mock_scroll.side_effect = [all_points, all_points, cluster_zero_points]

        detail = clustering_service.get_cluster_detail(0)

        assert detail.total_clusters == 2
        assert detail.previous_cluster_id is None
        assert detail.next_cluster_id == 1
        assert detail.photos[0].file_path == "a.jpg"
        assert detail.representative_photos[0].file_path == "a.jpg"


class TestClustersRouter:
    """Tests for the cluster browsing API endpoints."""

    @patch("app.services.clip_service._model", new=MagicMock())
    @patch("app.services.qdrant_service.get_client")
    @patch("app.services.clip_service.get_model")
    @patch("app.routers.index.get_progress_snapshot")
    @patch("app.services.clustering_service.get_cluster_catalog")
    def test_list_clusters_returns_ready_catalog(
        self,
        mock_catalog,
        mock_progress,
        mock_get_model,
        mock_get_client,
    ):
        """GET /api/clusters returns ready data for the browse page."""
        from app.main import app
        from app.services import clustering_service
        from fastapi.testclient import TestClient

        mock_progress.return_value = {
            "status": "idle",
            "stage": "idle",
            "cluster_error": None,
        }
        mock_catalog.return_value = clustering_service.ClusterCatalogData(
            status="ready",
            total_clusters=1,
            total_photos=3,
            clusters=[
                clustering_service.ClusterSummaryData(
                    cluster_id=0,
                    size=3,
                    representative_photos=[
                        clustering_service.ClusterPhotoData(
                            file_path="a.jpg",
                            filename="a.jpg",
                            score=0.99,
                        )
                    ],
                )
            ],
        )

        client = TestClient(app)
        response = client.get("/api/clusters")

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"
        assert data["total_clusters"] == 1
        assert data["clusters"][0]["cluster_id"] == 0

    @patch("app.services.clip_service._model", new=MagicMock())
    @patch("app.services.qdrant_service.get_client")
    @patch("app.services.clip_service.get_model")
    @patch("app.routers.index.get_progress_snapshot")
    def test_get_cluster_returns_409_while_building(
        self,
        mock_progress,
        mock_get_model,
        mock_get_client,
    ):
        """GET /api/clusters/<id> is unavailable during cluster rebuilds."""
        from app.main import app
        from fastapi.testclient import TestClient

        mock_progress.return_value = {
            "status": "running",
            "stage": "clustering",
            "cluster_error": None,
        }

        client = TestClient(app)
        response = client.get("/api/clusters/0")

        assert response.status_code == 409
        assert "rebuilt" in response.json()["detail"].lower()


class TestIndexRouterClustering:
    """Tests for indexing results that include clustering information."""

    def setup_method(self):
        """Reset router state before each test."""
        from app.routers import index as index_module

        if index_module._run_lock.locked():
            index_module._run_lock.release()
        index_module._cancel_event.clear()
        index_module._progress.update(
            {
                "status": "idle",
                "stage": "idle",
                "current": 0,
                "total": 0,
                "indexed": 0,
                "skipped": 0,
                "errors": 0,
                "removed": 0,
                "started_at": 0.0,
                "elapsed_seconds": 0.0,
                "eta_seconds": None,
                "cluster_error": None,
                "result": None,
            }
        )

    @patch("app.services.clustering_service.rebuild_clusters")
    @patch("app.services.qdrant_service.get_indexed_count")
    @patch("app.services.qdrant_service.upsert_embeddings")
    @patch("app.services.qdrant_service.get_indexed_paths")
    @patch("app.services.clip_service.encode_image")
    def test_run_indexing_sets_total_clusters_on_complete(
        self,
        mock_encode_image,
        mock_get_paths,
        mock_upsert,
        mock_get_count,
        mock_rebuild,
    ):
        """Successful indexing stores cluster counts in the final status."""
        import tempfile

        from app.routers import index as index_module
        from app.services.clustering_service import ClusterBuildResult

        mock_encode_image.return_value = [0.1, 0.2]
        mock_get_paths.return_value = set()
        mock_get_count.return_value = 1
        mock_rebuild.return_value = ClusterBuildResult(
            total_clusters=4,
            total_photos=1,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            image_path = Path(tmpdir) / "photo.jpg"
            image_path.write_bytes(b"jpg")
            index_module._run_lock.acquire()
            try:
                index_module._run_indexing(Path(tmpdir), cleanup=False)
            finally:
                if index_module._run_lock.locked():
                    index_module._run_lock.release()

        assert mock_upsert.called
        assert index_module._progress["status"] == "complete"
        assert index_module._progress["result"].total_clusters == 4
        assert index_module._progress["cluster_error"] is None
