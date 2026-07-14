import json
from collections.abc import Iterable
from typing import Any

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
            recipe = self._convert_recipe_data(
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

        return ImportResult(
            status=ImportStatus.SUCCESS,
            recipe=recipe,
            extractor=self.extractor_name,
            confidence=0.95,
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
    ) -> Recipe:
        title = recipe_data["name"]

        ingredients = self._normalize_ingredients(recipe_data["recipeIngredient"])
        instructions = self._normalize_instructions(recipe_data["recipeInstructions"])

        return Recipe(
            title=title,
            source_type=SourceType.WEBSITE,
            source_url=source_url,
            source_name=self._parse_source_name(recipe_data),
            extractor=self.extractor_name,
            servings=self._parse_servings(recipe_data.get("recipeYield")),
            ingredients=ingredients,
            instructions=instructions,
        )

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
    def _parse_servings(value: Any) -> int | None:
        if isinstance(value, int):
            return value if value > 0 else None

        if isinstance(value, str):
            digits = "".join(character for character in value if character.isdigit())

            if digits:
                servings = int(digits)
                return servings if servings > 0 else None

        return None

    @staticmethod
    def _normalize_ingredients(value: Any) -> list[Ingredient]:
        if isinstance(value, str):
            raw_values = [value]
        elif isinstance(value, list):
            raw_values = value
        else:
            return []

        ingredients: list[Ingredient] = []

        for item in raw_values:
            if not isinstance(item, str):
                continue

            normalized = item.strip()

            if not normalized:
                continue

            ingredients.append(
                Ingredient(
                    original_text=normalized,
                    name=normalized,
                )
            )

        return ingredients

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
