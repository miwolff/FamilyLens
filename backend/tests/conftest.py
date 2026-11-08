"""Pytest configuration: mock heavy ML dependencies so tests run
without installing torch/sentence-transformers/Pillow locally."""

import sys
import types
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Stub out heavy dependencies before any app module is imported.
# The actual behaviour is tested via mocks in individual test cases.
# ---------------------------------------------------------------------------

if "torch" not in sys.modules:
    torch_stub = types.ModuleType("torch")

    class Tensor:  # noqa: D401 - tiny stub for SciPy/sklearn checks
        """Torch Tensor stub used by test imports."""

    torch_stub.Tensor = Tensor
    sys.modules["torch"] = torch_stub

for _mod in [
    "torchvision",
    "PIL",
    "PIL.Image",
    "rawpy",
    "sentence_transformers",
]:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()


# ---------------------------------------------------------------------------
# Shared fixtures. Imports of app modules happen inside fixtures so that the
# stubs above are installed first.
# ---------------------------------------------------------------------------
from pathlib import Path  # noqa: E402
from types import SimpleNamespace  # noqa: E402
from unittest.mock import patch  # noqa: E402

import pytest  # noqa: E402


@pytest.fixture
def api():
    """A TestClient with the CLIP model and Qdrant client mocked out.

    Exposes ``client``, ``qdrant`` (the mocked QdrantClient) and ``model``
    (the mocked SentenceTransformer).
    """
    from fastapi.testclient import TestClient

    from app.main import app

    with (
        patch("app.services.clip_service._model", new=MagicMock()),
        patch("app.services.qdrant_service.get_client") as get_client,
        patch("app.services.clip_service.get_model") as get_model,
    ):
        yield SimpleNamespace(
            client=TestClient(app),
            qdrant=get_client.return_value,
            model=get_model.return_value,
        )


@pytest.fixture
def photos_root(tmp_path, monkeypatch) -> Path:
    """Point the configured photos directory at a temporary folder."""
    from app.config import settings
    from app.routers import index as index_module

    root = (tmp_path / "photos").resolve()
    root.mkdir()
    monkeypatch.setattr(settings, "photos_dir", str(root))
    monkeypatch.setattr(index_module, "PHOTOS_ROOT", root)
    return root


@pytest.fixture
def index_state():
    """Reset the indexing router's module-level state around a test."""
    from app.routers import index as index_module

    def reset() -> None:
        if index_module._run_lock.locked():
            index_module._run_lock.release()
        index_module._cancel_event.clear()
        index_module.reset_progress_state()

    reset()
    yield index_module
    reset()
