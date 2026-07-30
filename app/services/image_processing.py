from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from uuid import UUID

from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ALLOWED_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_PIL_FORMATS = {"JPEG", "PNG", "WEBP"}


class ImageValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class NormalizedImage:
    content: bytes
    width: int
    height: int
    content_type: str = "image/jpeg"
    extension: str = ".jpg"


def normalize_recipe_image(
    *,
    content: bytes,
    filename: str,
    content_type: str | None,
    max_bytes: int,
    max_dimension: int,
) -> NormalizedImage:
    extension = Path(filename).suffix.casefold()

    if extension not in ALLOWED_IMAGE_EXTENSIONS:
        raise ImageValidationError(
            "Alleen JPEG-, PNG- en WebP-afbeeldingen worden ondersteund."
        )
    if content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise ImageValidationError(
            "Het MIME-type van de afbeelding is niet toegestaan."
        )
    if not content:
        raise ImageValidationError("De afbeelding is leeg.")
    if len(content) > max_bytes:
        raise ImageValidationError(
            f"De afbeelding mag maximaal {max_bytes // (1024 * 1024)} MB groot zijn."
        )

    try:
        with Image.open(BytesIO(content)) as candidate:
            candidate.verify()

        with Image.open(BytesIO(content)) as source:
            if source.format not in ALLOWED_PIL_FORMATS:
                raise ImageValidationError(
                    "Het bestand bevat geen ondersteunde afbeelding."
                )

            normalized = ImageOps.exif_transpose(source)
            normalized.thumbnail(
                (max_dimension, max_dimension),
                Image.Resampling.LANCZOS,
            )
            rgb_image = _to_rgb(normalized)
            output = BytesIO()
            rgb_image.save(
                output,
                format="JPEG",
                quality=90,
                optimize=True,
            )
    except (UnidentifiedImageError, OSError) as exc:
        raise ImageValidationError(
            "Het bestand kon niet als afbeelding worden gelezen."
        ) from exc

    return NormalizedImage(
        content=output.getvalue(),
        width=rgb_image.width,
        height=rgb_image.height,
    )


def _to_rgb(image: Image.Image) -> Image.Image:
    if image.mode == "RGB":
        return image.copy()

    if image.mode in {"RGBA", "LA"} or (
        image.mode == "P" and "transparency" in image.info
    ):
        rgba = image.convert("RGBA")
        background = Image.new("RGB", rgba.size, "white")
        background.paste(rgba, mask=rgba.getchannel("A"))
        return background

    return image.convert("RGB")


class TemporaryImageStorage:
    def __init__(self, imports_path: Path) -> None:
        self.imports_path = imports_path

    def save(self, *, import_id: UUID, image: NormalizedImage) -> Path:
        directory = self.imports_path / "pending-images"
        directory.mkdir(parents=True, exist_ok=True)
        destination = directory / f"{import_id}{image.extension}"
        destination.write_bytes(image.content)
        return destination
