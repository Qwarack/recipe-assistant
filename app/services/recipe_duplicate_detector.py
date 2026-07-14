from pathlib import Path

import yaml


class RecipeDuplicateDetector:
    def __init__(self, recipes_path: Path) -> None:
        self.recipes_path = recipes_path

    def find_by_source_url(
        self,
        source_url: str,
    ) -> Path | None:
        if not self.recipes_path.exists():
            return None

        for recipe_path in self.recipes_path.glob("*.md"):
            frontmatter = self._read_frontmatter(recipe_path)

            if frontmatter.get("source_url") == source_url:
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
