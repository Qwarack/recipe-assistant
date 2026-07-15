from pathlib import Path
from typing import Any

import yaml

from app.models.import_result import (
    ImportResult,
    ImportStatus,
    ImportWarning,
)
from app.models.recipe import Ingredient, Recipe, SourceType
from app.services.ingredient_parser import parse_ingredient_line_with_warnings


class MarkdownRecipeImporter:
    extractor_name = "markdown"

    def import_recipe(self, source: Path) -> ImportResult:
        validation_result = self._validate_source(source)

        if validation_result is not None:
            return validation_result

        try:
            content = source.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return self._failure(
                source=source,
                code="markdown_encoding_error",
                message="The Markdown file could not be read as UTF-8.",
            )
        except OSError as exc:
            return self._failure(
                source=source,
                code="markdown_read_error",
                message=f"Could not read the Markdown file: {exc}",
            )

        try:
            frontmatter, body = self._split_document(content)
        except ValueError as exc:
            return self._failure(
                source=source,
                code="markdown_frontmatter_invalid",
                message=str(exc),
            )

        try:
            recipe, warnings = self._build_recipe(
                frontmatter=frontmatter,
                body=body,
                source=source,
            )
        except (TypeError, ValueError) as exc:
            return self._failure(
                source=source,
                code="markdown_recipe_invalid",
                message=f"Could not create a recipe: {exc}",
            )

        status = ImportStatus.PARTIAL if warnings else ImportStatus.SUCCESS

        return ImportResult(
            status=status,
            recipe=recipe,
            warnings=warnings,
            extractor=self.extractor_name,
            raw_input_reference=str(source),
        )

    def _validate_source(
        self,
        source: Path,
    ) -> ImportResult | None:
        if not source.exists():
            return self._failure(
                source=source,
                code="markdown_file_not_found",
                message=f"Markdown file does not exist: {source}",
            )

        if not source.is_file():
            return self._failure(
                source=source,
                code="markdown_path_not_file",
                message=f"Markdown path is not a file: {source}",
            )

        if source.suffix.casefold() != ".md":
            return self._failure(
                source=source,
                code="unsupported_markdown_file_type",
                message=(f"Expected a .md file, received: {source.suffix or '<none>'}"),
            )

        return None

    @staticmethod
    def _split_document(
        content: str,
    ) -> tuple[dict[str, Any], str]:
        if not content.startswith("---\n"):
            raise ValueError("Markdown recipe is missing YAML frontmatter.")

        parts = content.split("---", maxsplit=2)

        if len(parts) != 3:
            raise ValueError("Markdown frontmatter is not properly closed.")

        raw_frontmatter = parts[1]
        body = parts[2].lstrip("\n")

        parsed = yaml.safe_load(raw_frontmatter)

        if not isinstance(parsed, dict):
            raise ValueError("Markdown frontmatter must contain a YAML mapping.")

        return parsed, body

    def _build_recipe(
        self,
        frontmatter: dict[str, Any],
        body: str,
        source: Path,
    ) -> tuple[Recipe, list[ImportWarning]]:
        title = frontmatter.get("title")

        if not isinstance(title, str) or not title.strip():
            raise ValueError("Markdown frontmatter must contain a title.")

        ingredients, warnings = self._parse_ingredients(body)
        instructions = self._parse_instructions(body)

        recipe = Recipe(
            title=title.strip(),
            source_type=SourceType.MARKDOWN,
            source_url=frontmatter.get("source_url"),
            source_name=frontmatter.get("source_name"),
            extractor=self.extractor_name,
            servings=frontmatter.get("servings"),
            prep_time_minutes=frontmatter.get("prep_time_minutes"),
            cook_time_minutes=frontmatter.get("cook_time_minutes"),
            total_time_minutes=frontmatter.get("total_time_minutes"),
            tags=frontmatter.get("tags", []),
            meal_types=frontmatter.get("meal_types", []),
            ingredients=ingredients,
            instructions=instructions,
        )

        return recipe, warnings

    @staticmethod
    def _parse_ingredients(
        body: str,
    ) -> tuple[list[Ingredient], list[ImportWarning]]:
        lines = MarkdownRecipeImporter._section_lines(
            body=body,
            heading="## Ingrediënten",
        )

        ingredients: list[Ingredient] = []
        warnings: list[ImportWarning] = []

        for line in lines:
            stripped = line.strip()

            if not stripped.startswith("- "):
                continue

            raw_text = stripped.removeprefix("- ").strip()

            if not raw_text:
                continue

            parse_result = parse_ingredient_line_with_warnings(raw_text)

            ingredients.append(parse_result.ingredient)
            warnings.extend(
                ImportWarning(
                    code=warning.code,
                    message=warning.message,
                )
                for warning in parse_result.warnings
            )

        return ingredients, warnings

    @staticmethod
    def _parse_instructions(
        body: str,
    ) -> list[str]:
        lines = MarkdownRecipeImporter._section_lines(
            body=body,
            heading="## Bereiding",
        )

        instructions: list[str] = []

        for line in lines:
            stripped = line.strip()

            if not stripped:
                continue

            number, separator, text = stripped.partition(".")

            if separator and number.isdigit() and text.strip():
                instructions.append(text.strip())

        return instructions

    @staticmethod
    def _section_lines(
        body: str,
        heading: str,
    ) -> list[str]:
        lines = body.splitlines()
        collected: list[str] = []
        in_section = False

        for line in lines:
            if line.strip() == heading:
                in_section = True
                continue

            if in_section and line.startswith("## "):
                break

            if in_section:
                collected.append(line)

        return collected

    @staticmethod
    def _failure(
        source: Path,
        code: str,
        message: str,
    ) -> ImportResult:
        return ImportResult(
            status=ImportStatus.FAILED,
            warnings=[
                ImportWarning(
                    code=code,
                    message=message,
                )
            ],
            extractor="markdown",
            raw_input_reference=str(source),
        )
