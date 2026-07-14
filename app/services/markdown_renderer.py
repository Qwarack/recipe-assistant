from pathlib import Path
from typing import Any

import yaml
from app.models.recipe import Recipe
from jinja2 import Environment, FileSystemLoader, StrictUndefined

TEMPLATE_DIRECTORY = Path(__file__).parent.parent / "templates"


class RecipeMarkdownRenderer:
    def __init__(self) -> None:
        self._environment = Environment(
            loader=FileSystemLoader(TEMPLATE_DIRECTORY),
            undefined=StrictUndefined,
            autoescape=False,
            keep_trailing_newline=True,
        )
        self._template = self._environment.get_template("recipe.md.j2")

    def render(self, recipe: Recipe) -> str:
        frontmatter_data = self._build_frontmatter(recipe)
        frontmatter = yaml.safe_dump(
            frontmatter_data,
            allow_unicode=True,
            sort_keys=False,
        ).strip()

        return self._template.render(
            recipe=recipe,
            frontmatter=frontmatter,
        )

    @staticmethod
    def _build_frontmatter(recipe: Recipe) -> dict[str, Any]:
        return {
            "id": str(recipe.id),
            "type": "recipe",
            "title": recipe.title,
            "source_type": recipe.source_type.value,
            "source_url": (
                str(recipe.source_url) if recipe.source_url is not None else None
            ),
            "source_name": recipe.source_name,
            "extractor": recipe.extractor,
            "imported_at": (
                recipe.imported_at.isoformat()
                if recipe.imported_at is not None
                else None
            ),
            "servings": recipe.servings,
            "prep_time_minutes": recipe.prep_time_minutes,
            "cook_time_minutes": recipe.cook_time_minutes,
            "total_time_minutes": recipe.total_time_minutes,
            "tags": recipe.tags,
        }
