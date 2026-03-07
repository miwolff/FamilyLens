import hashlib
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
        mock_pil.open.return_value.convert.return_value = mock_img

        clip_service.load_model()
        result = clip_service.encode_image(Path("/test/photo.jpg"))

        assert isinstance(result, list)
        assert len(result) == 512
        mock_pil.open.assert_called_once_with(Path("/test/photo.jpg"))
        mock_pil.open.return_value.convert.assert_called_once_with(
            "RGB"
        )
        mock_model.encode.assert_called_once_with(
            mock_img, normalize_embeddings=True
        )

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
        mock_client.get_collections.return_value.collections = [
            mock_coll
        ]
        mock_get.return_value = mock_client

        ensure_collection()
        mock_client.create_collection.assert_not_called()

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
    def test_serve_photo_path_traversal(
        self, mock_get_model, mock_get_client
    ):
        """Path traversal attempts are blocked."""
        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app, raise_server_exceptions=False)
        response = client.get("/api/photos/../../etc/passwd")
        assert response.status_code in (403, 404)


class TestIndexRouter:
    """Tests for the index API endpoint."""

    @patch("app.services.clip_service._model", new=MagicMock())
    @patch("app.services.qdrant_service.get_client")
    @patch("app.services.clip_service.get_model")
    def test_index_missing_folder_returns_error(
        self, mock_get_model, mock_get_client
    ):
        """Indexing a nonexistent folder returns an error."""
        from fastapi.testclient import TestClient

        from app.main import app

        client = TestClient(app, raise_server_exceptions=False)
        response = client.post(
            "/api/index",
            json={"folder": "/nonexistent/folder"},
        )
        assert response.status_code == 500
