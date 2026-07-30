from dataclasses import dataclass
from pathlib import Path

ALLOWED_ATTACHMENT_EXTENSIONS = {
    ".md",
    ".txt",
    ".html",
    ".htm",
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
}

MAX_ATTACHMENT_SIZE_BYTES = 2 * 1024 * 1024
MAX_IMAGE_ATTACHMENT_SIZE_BYTES = 10 * 1024 * 1024
IMAGE_ATTACHMENT_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}


@dataclass(slots=True)
class AttachmentValidationResult:
    valid: bool
    error: str | None = None


def validate_recipe_attachment(
    *,
    filename: str,
    size_bytes: int,
    content_type: str | None = None,
) -> AttachmentValidationResult:
    extension = Path(filename).suffix.casefold()

    if extension not in ALLOWED_ATTACHMENT_EXTENSIONS:
        return AttachmentValidationResult(
            valid=False,
            error=(
                "Alleen Markdown-, tekst-, HTML-, JPEG-, PNG- en "
                "WebP-bestanden worden ondersteund."
            ),
        )

    if size_bytes <= 0:
        return AttachmentValidationResult(
            valid=False,
            error="Het bestand is leeg.",
        )

    if extension in IMAGE_ATTACHMENT_EXTENSIONS:
        if content_type is not None and content_type not in IMAGE_CONTENT_TYPES:
            return AttachmentValidationResult(
                valid=False,
                error="Het MIME-type van de afbeelding is niet toegestaan.",
            )
        if size_bytes > MAX_IMAGE_ATTACHMENT_SIZE_BYTES:
            return AttachmentValidationResult(
                valid=False,
                error="De afbeelding mag maximaal 10 MB groot zijn.",
            )
        return AttachmentValidationResult(valid=True)

    if size_bytes > MAX_ATTACHMENT_SIZE_BYTES:
        return AttachmentValidationResult(
            valid=False,
            error="Het bestand mag maximaal 2 MB groot zijn.",
        )

    return AttachmentValidationResult(valid=True)
