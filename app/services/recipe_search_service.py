from pathlib import Path

import yaml
from app.models.recipe_search import RecipeSearchResult


class RecipeSearchService:
    def __init__(self, recipes_path: Path) -> None:
        self.recipes_path = recipes_path

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
    ) -> list[RecipeSearchResult]:
        normalized_query = query.strip().casefold()

        if not normalized_query:
            return []

        results: list[RecipeSearchResult] = []

        for recipe_path in self.recipes_path.glob("*.md"):
            result = self._match_recipe(
                recipe_path,
                normalized_query,
            )

            if result is not None:
                results.append(result)

            if len(results) >= limit:
                break

        return results

    def _match_recipe(
        self,
        recipe_path: Path,
        normalized_query: str,
    ) -> RecipeSearchResult | None:
        text = recipe_path.read_text(encoding="utf-8")
        metadata = self._read_frontmatter(text)

        title = str(metadata.get("title") or recipe_path.stem)

        searchable_text = " ".join(
            [
                title,
                str(metadata.get("tags", "")),
                str(metadata.get("meal_types", "")),
            ]
        ).casefold()

        if normalized_query not in searchable_text:
            return None

        source_url = metadata.get("source_url")

        return RecipeSearchResult(
            identifier=recipe_path.stem,
            title=title,
            path=str(recipe_path),
            source_url=source_url,
        )

    def _read_frontmatter(
        self,
        text: str,
    ) -> dict[str, object]:
        if not text.startswith("---"):
            return {}

        parts = text.split("---", maxsplit=2)

        if len(parts) < 3:
            return {}

        metadata = yaml.safe_load(parts[1])

        if not isinstance(metadata, dict):
            return {}

        return metadata
