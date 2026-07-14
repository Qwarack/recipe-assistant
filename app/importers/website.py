import json
from collections.abc import Iterable
from datetime import timedelta
from typing import Any

import isodate
from bs4 import BeautifulSoup
from pydantic import ValidationError

from app.core.http_client import HttpFetchError, SafeHttpClient
from app.importers.base import RecipeImporter
from app.models.import_result import (
    ImportResult,
    ImportStatus,
    ImportWarning,
)
from app.models.recipe import Ingredient, Recipe, SourceType
from app.services.ingredient_parser import (
    parse_ingredient_line_with_warnings,
)
from app.services.servings_parser import parse_servings


class WebsiteRecipeImporter(RecipeImporter[str]):
    extractor_name = "schema_org"

    def __init__(self, http_client: SafeHttpClient) -> None:
        self.http_client = http_client

    def import_recipe(self, source: str) -> ImportResult:
        try:
            html = self.http_client.get_text(source)
        except HttpFetchError as exc:
            return ImportResult(
                status=ImportStatus.FAILED,
                extractor=self.extractor_name,
                warnings=[
                    ImportWarning(
                        code="http_fetch_failed",
                        message=str(exc),
                        field="source_url",
                    )
                ],
            )

        recipe_data = self._find_recipe_json_ld(html)

        if recipe_data is None:
            return ImportResult(
                status=ImportStatus.FAILED,
                extractor=self.extractor_name,
                warnings=[
                    ImportWarning(
                        code="recipe_json_ld_not_found",
                        message="No schema.org Recipe JSON-LD was found",
                    )
                ],
            )

        try:
            recipe, warnings = self._convert_recipe_data(
                recipe_data=recipe_data,
                source_url=source,
            )
        except (KeyError, TypeError, ValueError, ValidationError) as exc:
            return ImportResult(
                status=ImportStatus.FAILED,
                extractor=self.extractor_name,
                warnings=[
                    ImportWarning(
                        code="recipe_conversion_failed",
                        message=str(exc),
                    )
                ],
            )

        status = ImportStatus.PARTIAL if warnings else ImportStatus.SUCCESS

        return ImportResult(
            status=status,
            recipe=recipe,
            extractor=self.extractor_name,
            confidence=0.75 if warnings else 0.95,
            warnings=warnings,
        )

    def _find_recipe_json_ld(
        self,
        html: str,
    ) -> dict[str, Any] | None:
        soup = BeautifulSoup(html, "html.parser")

        scripts = soup.find_all(
            "script",
            attrs={"type": "application/ld+json"},
        )

        for script in scripts:
            if not script.string:
                continue

            try:
                data = json.loads(script.string)
            except json.JSONDecodeError:
                continue

            for item in self._walk_json_ld(data):
                if self._is_recipe(item):
                    return item

        return None

    def _walk_json_ld(
        self,
        value: Any,
    ) -> Iterable[dict[str, Any]]:
        if isinstance(value, dict):
            yield value

            graph = value.get("@graph")

            if isinstance(graph, list):
                for item in graph:
                    yield from self._walk_json_ld(item)

        elif isinstance(value, list):
            for item in value:
                yield from self._walk_json_ld(item)

    @staticmethod
    def _is_recipe(value: dict[str, Any]) -> bool:
        recipe_type = value.get("@type")

        if isinstance(recipe_type, str):
            return recipe_type == "Recipe"

        if isinstance(recipe_type, list):
            return "Recipe" in recipe_type

        return False

    def _convert_recipe_data(
        self,
        *,
        recipe_data: dict[str, Any],
        source_url: str,
    ) -> tuple[Recipe, list[ImportWarning]]:
        title = recipe_data["name"]

        ingredients, warnings = self._normalize_ingredients(
            recipe_data["recipeIngredient"]
        )
        instructions = self._normalize_instructions(recipe_data["recipeInstructions"])

        recipe = Recipe(
            title=title,
            source_type=SourceType.WEBSITE,
            source_url=source_url,
            source_name=self._parse_source_name(recipe_data),
            extractor=self.extractor_name,
            servings=parse_servings(recipe_data.get("recipeYield")),
            prep_time_minutes=self._parse_duration_minutes(recipe_data.get("prepTime")),
            cook_time_minutes=self._parse_duration_minutes(recipe_data.get("cookTime")),
            total_time_minutes=self._parse_duration_minutes(
                recipe_data.get("totalTime")
            ),
            ingredients=ingredients,
            instructions=instructions,
            tags=self._parse_tags(recipe_data),
        )

        return recipe, warnings

    def _walk_instructions(
        self,
        value: Any,
    ) -> Iterable[str]:
        if isinstance(value, str):
            yield value
            return

        if isinstance(value, list):
            for item in value:
                yield from self._walk_instructions(item)

            return

        if not isinstance(value, dict):
            return

        instruction_type = value.get("@type")

        if instruction_type == "HowToSection":
            section_name = value.get("name")

            if isinstance(section_name, str) and section_name.strip():
                yield section_name

            yield from self._walk_instructions(value.get("itemListElement", []))
            return

        text = value.get("text")

        if isinstance(text, str):
            yield text

        nested_items = value.get("itemListElement")

        if nested_items is not None:
            yield from self._walk_instructions(nested_items)

    def _normalize_instructions(
        self,
        raw_instructions: Any,
    ) -> list[str]:
        instructions: list[str] = []

        for text in self._walk_instructions(raw_instructions):
            normalized = text.strip()

            if normalized:
                instructions.append(normalized)

        return instructions

    @staticmethod
    def _normalize_ingredients(
        value: Any,
    ) -> tuple[list[Ingredient], list[ImportWarning]]:
        if isinstance(value, str):
            raw_values = [value]
        elif isinstance(value, list):
            raw_values = value
        else:
            return [], []

        ingredients: list[Ingredient] = []
        warnings: list[ImportWarning] = []

        for index, item in enumerate(raw_values):
            if not isinstance(item, str):
                continue

            normalized = item.strip()

            if not normalized:
                continue

            parse_result = parse_ingredient_line_with_warnings(normalized)
            ingredients.append(parse_result.ingredient)

            for warning in parse_result.warnings:
                warnings.append(
                    ImportWarning(
                        code=warning.code,
                        message=warning.message,
                        field=f"ingredients.{index}",
                    )
                )

        return ingredients, warnings

    @staticmethod
    def _parse_source_name(
        recipe_data: dict[str, Any],
    ) -> str | None:
        publisher = recipe_data.get("publisher")

        if isinstance(publisher, dict):
            name = publisher.get("name")

            if isinstance(name, str) and name.strip():
                return name.strip()

        author = recipe_data.get("author")

        if isinstance(author, dict):
            name = author.get("name")

            if isinstance(name, str) and name.strip():
                return name.strip()

        if isinstance(author, str) and author.strip():
            return author.strip()

        return None

    @staticmethod
    def _parse_duration_minutes(value: Any) -> int | None:
        if not isinstance(value, str) or not value.strip():
            return None

        try:
            duration = isodate.parse_duration(value.strip())
        except (isodate.ISO8601Error, ValueError):
            return None

        if not isinstance(duration, timedelta):
            return None

        total_seconds = duration.total_seconds()

        if total_seconds < 0:
            return None

        return round(total_seconds / 60)

    @staticmethod
    def _normalize_string_list(value: Any) -> list[str]:
        if isinstance(value, str):
            raw_values = value.split(",")
        elif isinstance(value, list):
            raw_values = value
        else:
            return []

        normalized_values: set[str] = set()

        for item in raw_values:
            if not isinstance(item, str):
                continue

            normalized = item.strip().lower()

            if normalized:
                normalized_values.add(normalized)

        return sorted(normalized_values)

    def _parse_tags(
        self,
        recipe_data: dict[str, Any],
    ) -> list[str]:
        tags: set[str] = set()

        for field_name in (
            "keywords",
            "recipeCategory",
            "recipeCuisine",
        ):
            tags.update(self._normalize_string_list(recipe_data.get(field_name)))

        return sorted(tags)
