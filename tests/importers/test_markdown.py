from pathlib import Path

from app.importers.markdown import MarkdownRecipeImporter
from app.models.import_result import ImportStatus
from app.models.recipe import SourceType


def test_imports_recipe_from_markdown(
    tmp_path: Path,
) -> None:
    markdown_path = tmp_path / "pasta.md"
    markdown_path.write_text(
        """---
title: Pasta Carbonara
source_url: https://example.com/carbonara
servings: 4
prep_time_minutes: 10
cook_time_minutes: 20
tags:
  - pasta
  - quick
---

# Pasta Carbonara

## Ingrediënten

- 400 g spaghetti
- 2 eieren

## Bereiding

1. Cook the pasta.
2. Mix with the eggs.
""",
        encoding="utf-8",
    )

    importer = MarkdownRecipeImporter()

    result = importer.import_recipe(markdown_path)

    assert result.status is ImportStatus.SUCCESS
    assert result.recipe is not None
    assert result.recipe.title == "Pasta Carbonara"
    assert result.recipe.source_type is SourceType.MARKDOWN
    assert result.recipe.servings == 4
    assert len(result.recipe.ingredients) == 2
    assert result.recipe.instructions == [
        "Cook the pasta.",
        "Mix with the eggs.",
    ]
    assert result.raw_input_reference == str(markdown_path)


def test_fails_when_markdown_has_no_frontmatter(
    tmp_path: Path,
) -> None:
    markdown_path = tmp_path / "recipe.md"
    markdown_path.write_text(
        "# Recept zonder frontmatter\n",
        encoding="utf-8",
    )

    importer = MarkdownRecipeImporter()

    result = importer.import_recipe(markdown_path)

    assert result.status is ImportStatus.FAILED
    assert result.recipe is None
    assert result.warnings[0].code == ("markdown_frontmatter_invalid")


def test_fails_when_markdown_has_no_title(
    tmp_path: Path,
) -> None:
    markdown_path = tmp_path / "recipe.md"
    markdown_path.write_text(
        """---
tags:
  - dinner
---

## Ingrediënten

- tomaat

## Bereiding

1. Snijd de tomaat.
""",
        encoding="utf-8",
    )

    importer = MarkdownRecipeImporter()

    result = importer.import_recipe(markdown_path)

    assert result.status is ImportStatus.FAILED
    assert result.warnings[0].code == ("markdown_recipe_invalid")


def test_rejects_non_markdown_file(
    tmp_path: Path,
) -> None:
    text_path = tmp_path / "recipe.txt"
    text_path.write_text(
        "Not Markdown",
        encoding="utf-8",
    )

    importer = MarkdownRecipeImporter()

    result = importer.import_recipe(text_path)

    assert result.status is ImportStatus.FAILED
    assert result.warnings[0].code == ("unsupported_markdown_file_type")
