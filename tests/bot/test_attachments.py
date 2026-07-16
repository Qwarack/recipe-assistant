from app.bot.attachments import (
    MAX_ATTACHMENT_SIZE_BYTES,
    validate_recipe_attachment,
)


def test_accepts_markdown_attachment() -> None:
    result = validate_recipe_attachment(
        filename="pasta.md",
        size_bytes=1024,
    )

    assert result.valid is True
    assert result.error is None


def test_rejects_unsupported_attachment() -> None:
    result = validate_recipe_attachment(
        filename="pasta.exe",
        size_bytes=1024,
    )

    assert result.valid is False
    assert result.error is not None


def test_rejects_oversized_attachment() -> None:
    result = validate_recipe_attachment(
        filename="pasta.txt",
        size_bytes=MAX_ATTACHMENT_SIZE_BYTES + 1,
    )

    assert result.valid is False
    assert result.error == ("Het bestand mag maximaal 2 MB groot zijn.")


def test_rejects_empty_attachment() -> None:
    result = validate_recipe_attachment(
        filename="pasta.html",
        size_bytes=0,
    )

    assert result.valid is False
    assert result.error == "Het bestand is leeg."
