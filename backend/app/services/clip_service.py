import logging
from pathlib import Path

from PIL import Image
from sentence_transformers import SentenceTransformer

from app.config import settings

logger = logging.getLogger(__name__)

_model: SentenceTransformer | None = None


def load_model() -> SentenceTransformer:
    """Load the CLIP model into memory (singleton)."""
    global _model
    if _model is None:
        logger.info("Loading CLIP model: %s", settings.clip_model_name)
        _model = SentenceTransformer(settings.clip_model_name)
        logger.info("CLIP model loaded successfully")
    return _model


def get_model() -> SentenceTransformer:
    """Return the loaded CLIP model. Raises if not loaded."""
    if _model is None:
        raise RuntimeError("CLIP model not loaded — call load_model() first")
    return _model


def encode_image(image_path: Path) -> list[float]:
    """Encode a single image file to a CLIP embedding vector."""
    model = get_model()
    with Image.open(image_path) as img:
        image = img.convert("RGB")
    embedding = model.encode(image, normalize_embeddings=True)
    return embedding.tolist()


def encode_text(query: str) -> list[float]:
    """Encode a text query to a CLIP embedding vector."""
    model = get_model()
    embedding = model.encode(query, normalize_embeddings=True)
    return embedding.tolist()
