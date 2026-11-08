from unittest.mock import patch


def test_health_returns_ok(api):
    """GET /health reports ok when the model and Qdrant are available."""
    response = api.client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "dependencies": {"clip": "up", "qdrant": "up"},
    }


def test_health_returns_degraded_when_qdrant_unavailable(api):
    """GET /health returns 503 when a dependency is down."""
    with patch(
        "app.main.qdrant_service.check_health", side_effect=RuntimeError("down")
    ):
        response = api.client.get("/health")

    assert response.status_code == 503
    assert response.json() == {
        "status": "degraded",
        "dependencies": {"clip": "up", "qdrant": "down"},
    }


def test_health_returns_degraded_when_model_not_loaded(api):
    """GET /health returns 503 before the CLIP model has loaded."""
    with patch("app.services.clip_service._model", None):
        response = api.client.get("/health")

    assert response.status_code == 503
    assert response.json()["dependencies"]["clip"] == "down"
