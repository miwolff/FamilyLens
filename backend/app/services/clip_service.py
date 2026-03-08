import logging
from io import BytesIO
from pathlib import Path

from PIL import Image
from sentence_transformers import SentenceTransformer

from app.config import settings

try:
    import rawpy
except ImportError:  # pragma: no cover - exercised only when dependency is absent
    rawpy = None

logger = logging.getLogger(__name__)

RAW_EXTENSIONS = {".dng", ".nef"}
SUPPORTED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", *RAW_EXTENSIONS}

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


def is_raw_image_path(image_path: Path) -> bool:
    """Return whether the given image path is a supported RAW format."""
    return image_path.suffix.lower() in RAW_EXTENSIONS


def load_image(image_path: Path) -> Image.Image:
    """Load a supported image as an RGB PIL image."""
    if is_raw_image_path(image_path):
        if rawpy is None:
            raise RuntimeError(
                "RAW support is not available because rawpy is not installed"
            )
        with rawpy.imread(str(image_path)) as raw:
            rgb_data = raw.postprocess()
        return Image.fromarray(rgb_data).convert("RGB")

    with Image.open(image_path) as img:
        return img.convert("RGB")


def render_preview(image_path: Path) -> bytes:
    """Render a browser-compatible JPEG preview for a supported image."""
    image = load_image(image_path)
    try:
        buffer = BytesIO()
        image.save(buffer, format="JPEG", quality=90)
        return buffer.getvalue()
    finally:
        image.close()


def encode_image(image_path: Path) -> list[float]:
    """Encode a single image file to a CLIP embedding vector."""
    model = get_model()
    image = load_image(image_path)
    try:
        embedding = model.encode(image, normalize_embeddings=True)
        return embedding.tolist()
    finally:
        image.close()


def encode_text(query: str) -> list[float]:
    """Encode a text query to a CLIP embedding vector."""
    model = get_model()
    embedding = model.encode(query, normalize_embeddings=True)
    return embedding.tolist()
