from pathlib import Path

import yaml
from app.utils.title_normalizer import normalize_title
from app.utils.url_normalizer import normalize_url


class RecipeDuplicateDetector:
    def __init__(self, recipes_path: Path) -> None:
        self.recipes_path = recipes_path

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

    @staticmethod
    def _read_frontmatter(recipe_path: Path) -> dict[str, object]:
        content = recipe_path.read_text(encoding="utf-8")

        if not content.startswith("---\n"):
            return {}

        try:
            _, raw_frontmatter, _ = content.split("---", maxsplit=2)
        except ValueError:
            return {}

        parsed = yaml.safe_load(raw_frontmatter)

        if not isinstance(parsed, dict):
            return {}

        return parsed

    def find_by_title(
        self,
        title: str,
    ) -> Path | None:
        if not self.recipes_path.exists():
            return None

        normalized_title = normalize_title(title)

        for recipe_path in self.recipes_path.glob("*.md"):
            frontmatter = self._read_frontmatter(recipe_path)
            existing_title = frontmatter.get("title")

            if not isinstance(existing_title, str):
                continue

            if normalize_title(existing_title) == normalized_title:
                return recipe_path

        return None
