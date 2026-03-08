"""Pytest configuration: mock heavy ML dependencies so tests run
without installing torch/sentence-transformers/Pillow locally."""

import sys
from unittest.mock import MagicMock

# ---------------------------------------------------------------------------
# Stub out heavy dependencies before any app module is imported.
# The actual behaviour is tested via mocks in individual test cases.
# ---------------------------------------------------------------------------

_HEAVY_MODULES = [
    "torch",
    "torchvision",
    "PIL",
    "PIL.Image",
    "rawpy",
    "sentence_transformers",
]

for _mod in _HEAVY_MODULES:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()
