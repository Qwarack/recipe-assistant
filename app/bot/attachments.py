from dataclasses import dataclass
from pathlib import Path

ALLOWED_ATTACHMENT_EXTENSIONS = {
    ".md",
    ".txt",
    ".html",
    ".htm",
}

MAX_ATTACHMENT_SIZE_BYTES = 2 * 1024 * 1024


@dataclass(slots=True)
class AttachmentValidationResult:
    valid: bool
    error: str | None = None


def validate_recipe_attachment(
    *,
    filename: str,
    size_bytes: int,
) -> AttachmentValidationResult:
    extension = Path(filename).suffix.casefold()

    if extension not in ALLOWED_ATTACHMENT_EXTENSIONS:
        return AttachmentValidationResult(
            valid=False,
            error=("Alleen Markdown-, tekst- en HTML-bestanden worden ondersteund."),
        )

    if size_bytes <= 0:
        return AttachmentValidationResult(
            valid=False,
            error="Het bestand is leeg.",
        )

    if size_bytes > MAX_ATTACHMENT_SIZE_BYTES:
        return AttachmentValidationResult(
            valid=False,
            error="Het bestand mag maximaal 2 MB groot zijn.",
        )

    return AttachmentValidationResult(valid=True)
