from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest


def test_search_returns_results(api):
    """POST /api/search encodes the query and returns formatted hits."""
    api.model.encode.return_value = np.zeros(512)
    hit = MagicMock(id=1, score=0.9)
    hit.payload = {"file_path": "beach.jpg", "filename": "beach.jpg"}
    api.qdrant.query_points.return_value.points = [hit]

    response = api.client.post("/api/search", json={"query": "  beach sunset "})

    assert response.status_code == 200
    data = response.json()
    assert data["query"] == "beach sunset"
    assert data["results"] == [
        {"file_path": "beach.jpg", "filename": "beach.jpg", "score": 0.9}
    ]


@pytest.mark.parametrize("query", ["", "   \n\t  ", "x" * 501])
def test_search_rejects_invalid_queries(api, query):
    """Empty, whitespace-only and over-long queries are rejected."""
    response = api.client.post("/api/search", json={"query": query})

    assert response.status_code == 422


def test_status_reports_count_and_limits(api):
    """GET /api/status exposes the photo count and the cluster limit."""
    api.qdrant.get_collection.return_value.points_count = 42

    response = api.client.get("/api/status")

    assert response.json() == {
        "indexed_photos": 42,
        "collection_name": "photos",
        "max_cluster_count": 1000,
    }


@pytest.mark.parametrize(
    ("name", "content", "media_type"),
    [
        ("test.jpg", b"\xff\xd8\xff" + b"\x00" * 10, "image/jpeg"),
        ("test.png", b"\x89PNG\r\n\x1a\n" + b"\x00" * 10, "image/png"),
    ],
)
def test_serve_photo_content_type(api, photos_root, name, content, media_type):
    """Photos are served with a content type matching their extension."""
    (photos_root / name).write_bytes(content)

    response = api.client.get(f"/api/photos/{name}")

    assert response.status_code == 200
    assert media_type in response.headers["content-type"]


def test_serve_photo_raw_preview(api, photos_root):
    """RAW files are served as a rendered JPEG preview."""
    raw_file = photos_root / "test.nef"
    raw_file.write_bytes(b"RAWDATA")

    with patch(
        "app.services.clip_service.render_preview", return_value=b"jpeg-preview"
    ) as render:
        response = api.client.get("/api/photos/test.nef")

    assert response.status_code == 200
    assert response.content == b"jpeg-preview"
    assert "image/jpeg" in response.headers["content-type"]
    render.assert_called_once_with(Path(raw_file).resolve())


def test_serve_photo_not_found(api, photos_root):
    """A missing file returns 404."""
    assert api.client.get("/api/photos/nope.jpg").status_code == 404


@pytest.mark.parametrize(
    "path", ["../secret.jpg", "1/../../secret.jpg", "%2e%2e/secret.jpg"]
)
def test_serve_photo_blocks_path_traversal(api, photos_root, path):
    """Paths escaping the photos root are never served."""
    (photos_root.parent / "secret.jpg").write_bytes(b"secret")

    response = api.client.get(f"/api/photos/{path}")

    assert response.status_code in (403, 404)
    assert response.content != b"secret"
