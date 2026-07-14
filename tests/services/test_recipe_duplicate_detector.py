from pathlib import Path

from app.services.recipe_duplicate_detector import (
    RecipeDuplicateDetector,
)


def test_finds_recipe_with_matching_source_url(
    tmp_path: Path,
) -> None:
    recipe_path = tmp_path / "pasta.md"
    recipe_path.write_text(
        """---
id: 12345678-1234-1234-1234-123456789abc
title: Pasta
source_url: https://example.com/pasta
---

# Pasta
""",
        encoding="utf-8",
    )

    detector = RecipeDuplicateDetector(tmp_path)

    result = detector.find_by_source_url("https://example.com/pasta")

    assert result == recipe_path


def test_returns_none_when_source_url_does_not_exist(
    tmp_path: Path,
) -> None:
    recipe_path = tmp_path / "pasta.md"
    recipe_path.write_text(
        """---
title: Pasta
source_url: https://example.com/pasta
---

# Pasta
""",
        encoding="utf-8",
    )

    detector = RecipeDuplicateDetector(tmp_path)

    result = detector.find_by_source_url("https://example.com/soup")

    assert result is None


def test_ignores_markdown_without_valid_frontmatter(
    tmp_path: Path,
) -> None:
    recipe_path = tmp_path / "notes.md"
    recipe_path.write_text(
        "# Gewone notitie\n",
        encoding="utf-8",
    )

    detector = RecipeDuplicateDetector(tmp_path)

    result = detector.find_by_source_url("https://example.com/pasta")

    assert result is None
