from pathlib import Path

import yaml
from app.models.recipe_detail import RecipeDetail


class RecipeDetailService:
    def __init__(self, recipes_path: Path) -> None:
        self.recipes_path = recipes_path

    def get_by_identifier(
        self,
        identifier: str,
    ) -> RecipeDetail | None:
        safe_identifier = Path(identifier).name
        recipe_path = self.recipes_path / f"{safe_identifier}.md"

        if not recipe_path.is_file():
            return None

        text = recipe_path.read_text(encoding="utf-8")
        metadata, markdown_body = self._split_frontmatter(text)

        return RecipeDetail(
            identifier=safe_identifier,
            title=str(metadata.get("title") or safe_identifier),
            ingredients=self._read_section(
                markdown_body,
                "Ingrediënten",
            ),
            instructions=self._read_numbered_section(
                markdown_body,
                "Bereiding",
            ),
            servings=self._optional_int(metadata.get("servings")),
            prep_time_minutes=self._optional_int(metadata.get("prep_time_minutes")),
            cook_time_minutes=self._optional_int(metadata.get("cook_time_minutes")),
            total_time_minutes=self._optional_int(metadata.get("total_time_minutes")),
            source_url=metadata.get("source_url"),
            tags=self._string_list(metadata.get("tags")),
            meal_types=self._string_list(metadata.get("meal_types")),
        )

    def _split_frontmatter(
        self,
        text: str,
    ) -> tuple[dict[str, object], str]:
        if not text.startswith("---"):
            return {}, text

        parts = text.split("---", maxsplit=2)

        if len(parts) < 3:
            return {}, text

        parsed = yaml.safe_load(parts[1])
        metadata = parsed if isinstance(parsed, dict) else {}

        return metadata, parts[2]

    def _read_section(
        self,
        markdown_body: str,
        heading: str,
    ) -> list[str]:
        lines = self._section_lines(
            markdown_body,
            heading,
        )

        return [
            line.removeprefix("- ").strip() for line in lines if line.startswith("- ")
        ]

    def _read_numbered_section(
        self,
        markdown_body: str,
        heading: str,
    ) -> list[str]:
        lines = self._section_lines(
            markdown_body,
            heading,
        )

        instructions: list[str] = []

        for line in lines:
            number, separator, value = line.partition(".")

            if separator and number.strip().isdigit() and value.strip():
                instructions.append(value.strip())

        return instructions

    def _section_lines(
        self,
        markdown_body: str,
        heading: str,
    ) -> list[str]:
        lines = markdown_body.splitlines()
        target_heading = f"## {heading}".casefold()

        section_start: int | None = None

        for index, line in enumerate(lines):
            if line.strip().casefold() == target_heading:
                section_start = index + 1
                break

        if section_start is None:
            return []

        section_lines: list[str] = []

        for line in lines[section_start:]:
            if line.startswith("## "):
                break

            stripped_line = line.strip()

            if stripped_line:
                section_lines.append(stripped_line)

        return section_lines

    def _optional_int(
        self,
        value: object,
    ) -> int | None:
        if value is None:
            return None

        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _string_list(
        self,
        value: object,
    ) -> list[str]:
        if not isinstance(value, list):
            return []

        return [str(item) for item in value if str(item).strip()]
