from pathlib import Path

from app.services.recipe_duplicate_detector import (
    RecipeDuplicateDetector,
)
from app.utils.url_normalizer import normalize_url


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


def find_by_source_url(
    self,
    source_url: str,
) -> Path | None:
    if not self.recipes_path.exists():
        return None

    normalized_source_url = normalize_url(source_url)

    for recipe_path in self.recipes_path.glob("*.md"):
        frontmatter = self._read_frontmatter(recipe_path)
        existing_source_url = frontmatter.get("source_url")

        if not isinstance(existing_source_url, str):
            continue

        if normalize_url(existing_source_url) == normalized_source_url:
            return recipe_path

    return None


def test_finds_recipe_with_equivalent_normalized_title(
    tmp_path: Path,
) -> None:
    recipe_path = tmp_path / "pasta.md"
    recipe_path.write_text(
        """---
title: Pasta Carbonara
source_url: null
---

# Pasta Carbonara
""",
        encoding="utf-8",
    )

    detector = RecipeDuplicateDetector(tmp_path)

    result = detector.find_by_title("  pasta   carbonara! ")

    assert result == recipe_path


def test_returns_none_when_title_does_not_match(
    tmp_path: Path,
) -> None:
    recipe_path = tmp_path / "pasta.md"
    recipe_path.write_text(
        """---
title: Pasta Carbonara
---

# Pasta Carbonara
""",
        encoding="utf-8",
    )

    detector = RecipeDuplicateDetector(tmp_path)

    result = detector.find_by_title("Tomatensoep")

    assert result is None


def test_finds_recipe_with_matching_content_hash(
    tmp_path: Path,
) -> None:
    recipe_path = tmp_path / "pasta.md"
    recipe_path.write_text(
        """---
title: Pasta Carbonara
content_hash: abc123
---

# Pasta Carbonara
""",
        encoding="utf-8",
    )

    detector = RecipeDuplicateDetector(tmp_path)

    result = detector.find_by_content_hash("abc123")

    assert result == recipe_path


def test_returns_none_when_content_hash_does_not_match(
    tmp_path: Path,
) -> None:
    recipe_path = tmp_path / "pasta.md"
    recipe_path.write_text(
        """---
title: Pasta Carbonara
content_hash: abc123
---

# Pasta Carbonara
""",
        encoding="utf-8",
    )

    detector = RecipeDuplicateDetector(tmp_path)

    result = detector.find_by_content_hash("different-hash")

    assert result is None
