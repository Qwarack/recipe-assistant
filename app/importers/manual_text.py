import re

from app.models.import_result import (
    ImportResult,
    ImportStatus,
    ImportWarning,
)
from app.models.recipe import Recipe, SourceType
from app.services.ingredient_parser import parse_ingredient_line

INGREDIENT_HEADINGS = {
    "ingrediënten",
    "ingredienten",
    "ingredients",
}

INSTRUCTION_HEADINGS = {
    "bereiding",
    "instructies",
    "werkwijze",
    "instructions",
    "method",
}

NUMBERED_STEP_PATTERN = re.compile(r"^\s*\d+[.)]\s*(.+)$")


class ManualTextRecipeImporter:
    extractor_name = "manual-text"

    def import_recipe(self, source: str) -> ImportResult:
        cleaned_source = source.strip()

        if not cleaned_source:
            return self._failure(
                code="manual_text_empty",
                message="The provided recipe text is empty.",
                source=source,
            )

        lines = [line.rstrip() for line in cleaned_source.splitlines()]

        title = self._find_title(lines)
        ingredient_lines = self._find_section(
            lines=lines,
            headings=INGREDIENT_HEADINGS,
        )
        instruction_lines = self._find_section(
            lines=lines,
            headings=INSTRUCTION_HEADINGS,
        )

        if title is None:
            return self._failure(
                code="manual_text_title_missing",
                message="No recipe title could be found.",
                source=source,
            )

        ingredients = [parse_ingredient_line(line) for line in ingredient_lines]

        instructions = [
            instruction
            for line in instruction_lines
            if (instruction := self._parse_instruction(line))
        ]

        try:
            recipe = Recipe(
                title=title,
                source_type=SourceType.MANUAL,
                extractor=self.extractor_name,
                ingredients=ingredients,
                instructions=instructions,
            )
        except ValueError as exc:
            return self._failure(
                code="manual_text_recipe_invalid",
                message=(f"The text could not be converted to a valid recipe: {exc}"),
                source=source,
            )

        return ImportResult(
            status=ImportStatus.SUCCESS,
            recipe=recipe,
            extractor=self.extractor_name,
            raw_input_reference=source,
        )

    @staticmethod
    def _find_title(
        lines: list[str],
    ) -> str | None:
        for line in lines:
            stripped = line.strip()

            if not stripped:
                continue

            normalized = stripped.rstrip(":").casefold()

            if (
                normalized not in INGREDIENT_HEADINGS
                and normalized not in INSTRUCTION_HEADINGS
            ):
                return stripped

        return None

    @staticmethod
    def _find_section(
        lines: list[str],
        headings: set[str],
    ) -> list[str]:
        collected: list[str] = []
        in_section = False

        all_headings = INGREDIENT_HEADINGS | INSTRUCTION_HEADINGS

        for line in lines:
            stripped = line.strip()
            normalized = stripped.rstrip(":").casefold()

            if normalized in headings:
                in_section = True
                continue

            if in_section and normalized in all_headings:
                break

            if not in_section or not stripped:
                continue

            collected.append(stripped)

        return collected

    @staticmethod
    def _parse_instruction(
        line: str,
    ) -> str | None:
        stripped = line.strip()

        if not stripped:
            return None

        numbered_match = NUMBERED_STEP_PATTERN.match(stripped)

        if numbered_match is not None:
            return numbered_match.group(1).strip()

        if stripped.startswith("- "):
            return stripped.removeprefix("- ").strip()

        return stripped

    @staticmethod
    def _failure(
        code: str,
        message: str,
        source: str,
    ) -> ImportResult:
        return ImportResult(
            status=ImportStatus.FAILED,
            warnings=[
                ImportWarning(
                    code=code,
                    message=message,
                )
            ],
            extractor="manual-text",
            raw_input_reference=source,
        )
