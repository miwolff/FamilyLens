from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.services import clip_service


@pytest.fixture
def model():
    """Install a mocked SentenceTransformer as the loaded model."""
    mock_model = MagicMock()
    with patch.object(clip_service, "_model", mock_model):
        yield mock_model


@patch("app.services.clip_service.SentenceTransformer")
def test_load_model_is_cached(mock_st_class):
    """The model is constructed once and reused on later calls."""
    with patch.object(clip_service, "_model", None):
        first = clip_service.load_model()
        second = clip_service.load_model()

    assert first is second is mock_st_class.return_value
    mock_st_class.assert_called_once_with("clip-ViT-B-32")


def test_get_model_not_loaded_raises():
    """get_model raises RuntimeError if the model is not loaded."""
    with (
        patch.object(clip_service, "_model", None),
        pytest.raises(RuntimeError, match="not loaded"),
    ):
        clip_service.get_model()


def test_encode_text(model):
    """encode_text returns a normalized embedding as a list of floats."""
    model.encode.return_value = np.random.randn(512)

    result = clip_service.encode_text("sunset on the beach")

    assert isinstance(result, list)
    assert len(result) == 512
    model.encode.assert_called_once_with(
        "sunset on the beach", normalize_embeddings=True
    )


def test_encode_images_uses_one_model_call(model):
    """encode_images encodes a whole batch with a single model call."""
    images = [MagicMock(), MagicMock(), MagicMock()]
    model.encode.return_value = np.zeros((3, 512))

    result = clip_service.encode_images(images)

    assert len(result) == 3
    model.encode.assert_called_once_with(
        images, batch_size=3, normalize_embeddings=True
    )


def test_encode_images_empty_skips_model(model):
    """encode_images returns [] without calling the model for no images."""
    assert clip_service.encode_images([]) == []
    model.encode.assert_not_called()


@patch("app.services.clip_service.Image")
def test_encode_image_downscales_and_closes(mock_pil, model):
    """encode_image loads a reduced-size RGB image and closes it."""
    model.encode.return_value = np.zeros((1, 512))
    opened = mock_pil.open.return_value.__enter__.return_value
    rgb = opened.convert.return_value

    result = clip_service.encode_image(Path("/test/photo.jpg"))

    assert len(result) == 512
    max_side = clip_service.ENCODE_MAX_SIDE
    opened.draft.assert_called_once_with("RGB", (max_side, max_side))
    opened.convert.assert_called_once_with("RGB")
    rgb.thumbnail.assert_called_once_with((max_side, max_side))
    rgb.close.assert_called_once_with()


@patch("app.services.clip_service.Image")
def test_load_image_full_size_by_default(mock_pil):
    """Without max_side the image is not downscaled (used for previews)."""
    opened = mock_pil.open.return_value.__enter__.return_value

    clip_service.load_image(Path("/test/photo.jpg"))

    opened.draft.assert_not_called()
    opened.convert.return_value.thumbnail.assert_not_called()


@patch("app.services.clip_service.rawpy")
@patch("app.services.clip_service.Image")
def test_load_raw_image_for_encoding(mock_image, mock_rawpy):
    """RAW files are demosaiced at half size when loaded for encoding."""
    raw = mock_rawpy.imread.return_value.__enter__.return_value
    raw.postprocess.return_value = "rgb-data"

    image = clip_service.load_image(Path("/test/photo.dng"), max_side=1024)

    mock_rawpy.imread.assert_called_once_with("/test/photo.dng")
    raw.postprocess.assert_called_once_with(half_size=True)
    mock_image.fromarray.assert_called_once_with("rgb-data")
    assert image is mock_image.fromarray.return_value.convert.return_value
    image.thumbnail.assert_called_once_with((1024, 1024))
