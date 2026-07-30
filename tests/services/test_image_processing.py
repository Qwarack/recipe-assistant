from io import BytesIO
from uuid import uuid4

import pytest
from app.services.image_processing import (
    ImageValidationError,
    TemporaryImageStorage,
    normalize_recipe_image,
)
from PIL import Image


def _image_bytes(
    *,
    image_format: str = "PNG",
    size: tuple[int, int] = (32, 16),
    mode: str = "RGB",
) -> bytes:
    output = BytesIO()
    color = (255, 0, 0, 128) if mode == "RGBA" else "red"
    Image.new(mode, size, color).save(output, format=image_format)
    return output.getvalue()


def test_normalize_image_resizes_and_converts_to_jpeg() -> None:
    result = normalize_recipe_image(
        content=_image_bytes(size=(400, 200), mode="RGBA"),
        filename="recipe.png",
        content_type="image/png",
        max_bytes=1024 * 1024,
        max_dimension=100,
    )

    assert result.content_type == "image/jpeg"
    assert result.width == 100
    assert result.height == 50

    with Image.open(BytesIO(result.content)) as image:
        assert image.format == "JPEG"
        assert image.mode == "RGB"


def test_normalize_image_applies_exif_rotation() -> None:
    output = BytesIO()
    source = Image.new("RGB", (40, 20), "white")
    exif = source.getexif()
    exif[274] = 6
    source.save(output, format="JPEG", exif=exif)

    result = normalize_recipe_image(
        content=output.getvalue(),
        filename="recipe.jpg",
        content_type="image/jpeg",
        max_bytes=1024 * 1024,
        max_dimension=100,
    )

    assert (result.width, result.height) == (20, 40)


@pytest.mark.parametrize(
    ("filename", "content_type", "content"),
    [
        ("recipe.gif", "image/gif", b"image"),
        ("recipe.png", "application/octet-stream", b"image"),
        ("recipe.png", "image/png", b"corrupt"),
        ("recipe.png", "image/png", b""),
    ],
)
def test_normalize_image_rejects_invalid_uploads(
    filename: str,
    content_type: str,
    content: bytes,
) -> None:
    with pytest.raises(ImageValidationError):
        normalize_recipe_image(
            content=content,
            filename=filename,
            content_type=content_type,
            max_bytes=1024,
            max_dimension=100,
        )


def test_normalize_image_rejects_oversized_upload() -> None:
    with pytest.raises(ImageValidationError, match="maximaal"):
        normalize_recipe_image(
            content=_image_bytes(),
            filename="recipe.png",
            content_type="image/png",
            max_bytes=1,
            max_dimension=100,
        )


def test_temporary_image_storage_uses_import_id(tmp_path) -> None:
    normalized = normalize_recipe_image(
        content=_image_bytes(),
        filename="recipe.png",
        content_type="image/png",
        max_bytes=1024 * 1024,
        max_dimension=100,
    )
    storage = TemporaryImageStorage(tmp_path)
    import_id = uuid4()
    destination = storage.save(import_id=import_id, image=normalized)

    assert destination == tmp_path / "pending-images" / f"{import_id}.jpg"
    assert destination.read_bytes() == normalized.content
