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


def is_model_loaded() -> bool:
    """Return whether the CLIP model is loaded in memory."""
    return _model is not None


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


# CLIP resizes inputs to 224 px, so decoding full-resolution photos only
# wastes memory. Images loaded for encoding are capped at this size, which
# keeps a batch of 32 photos around 100 MB instead of several GB.
ENCODE_MAX_SIDE = 1024


def load_image(image_path: Path, max_side: int | None = None) -> Image.Image:
    """Load a supported image as an RGB PIL image.

    If max_side is given, the image is downscaled (preserving aspect ratio)
    so that neither side exceeds it.
    """
    if is_raw_image_path(image_path):
        if rawpy is None:
            raise RuntimeError(
                "RAW support is not available because rawpy is not installed"
            )
        with rawpy.imread(str(image_path)) as raw:
            rgb_data = raw.postprocess(half_size=max_side is not None)
        image = Image.fromarray(rgb_data).convert("RGB")
    else:
        with Image.open(image_path) as img:
            if max_side is not None:
                # JPEG only: decode at a reduced scale, much faster.
                img.draft("RGB", (max_side, max_side))
            image = img.convert("RGB")

    if max_side is not None:
        image.thumbnail((max_side, max_side))
    return image


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
    image = load_image(image_path, max_side=ENCODE_MAX_SIDE)
    try:
        return encode_images([image])[0]
    finally:
        image.close()


def encode_images(images: list[Image.Image]) -> list[list[float]]:
    """Encode loaded images to CLIP embeddings in a single model call.

    Batching lets the model use vectorised kernels, which is much faster
    than encoding images one at a time.
    """
    if not images:
        return []
    model = get_model()
    embeddings = model.encode(
        images,
        batch_size=len(images),
        normalize_embeddings=True,
    )
    return embeddings.tolist()


def encode_text(query: str) -> list[float]:
    """Encode a text query to a CLIP embedding vector."""
    model = get_model()
    embedding = model.encode(query, normalize_embeddings=True)
    return embedding.tolist()
