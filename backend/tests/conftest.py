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
