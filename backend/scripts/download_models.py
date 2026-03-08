"""Download and cache CLIP models for faster container startup.

This script is intended to be run during Docker build to pre-download
the CLIP model into the image. This eliminates cold-start delays when
the container starts up.

Usage:
    python -m scripts.download_models

Environment variables:
    FAMILYLENS_CLIP_MODEL_NAME: Name of the CLIP model to download
                                 (default: clip-ViT-B-32)
    TRANSFORMERS_CACHE: Cache directory for HuggingFace models
                       (default: /app/.cache)
"""

import logging
import os
import sys

from sentence_transformers import SentenceTransformer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
)
logger = logging.getLogger(__name__)


def main() -> int:
    """Download the configured CLIP model.

    Returns:
        0 on success, 1 on failure.
    """
    # Get model name from environment, with default
    model_name = os.getenv(
        "FAMILYLENS_CLIP_MODEL_NAME",
        "clip-ViT-B-32",
    )

    # Get cache directory
    cache_dir = os.getenv("TRANSFORMERS_CACHE", "/app/.cache")

    logger.info("Starting CLIP model download")
    logger.info("Model: %s", model_name)
    logger.info("Cache directory: %s", cache_dir)

    try:
        # Create cache directory if it doesn't exist
        os.makedirs(cache_dir, exist_ok=True)
        logger.info("Cache directory ready: %s", cache_dir)

        # Download and cache the model
        logger.info("Downloading model %s...", model_name)
        model = SentenceTransformer(model_name)
        logger.info("Model downloaded and cached successfully")

        # Verify model is working by encoding a test string
        logger.info("Verifying model functionality...")
        test_embedding = model.encode("test")
        logger.info(
            "Model verification successful. Embedding dimension: %d",
            len(test_embedding),
        )

        logger.info("✓ CLIP model download complete")
        return 0

    except Exception as e:  # pylint: disable=broad-except
        logger.error("Failed to download CLIP model: %s", str(e))
        logger.error("Exception type: %s", type(e).__name__)
        return 1


if __name__ == "__main__":
    sys.exit(main())
