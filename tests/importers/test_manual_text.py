from app.importers.manual_text import (
    ManualTextRecipeImporter,
)
from app.models.import_result import ImportStatus
from app.models.recipe import SourceType


def test_imports_recipe_from_manual_text() -> None:
    source = """
Pasta Carbonara

Ingrediënten:
- 400 g spaghetti
- 2 eieren

Bereiding:
1. Kook de pasta.
2. Meng met de eieren.
"""

    importer = ManualTextRecipeImporter()

    result = importer.import_recipe(source)

    assert result.status is ImportStatus.SUCCESS
    assert result.recipe is not None
    assert result.recipe.title == "Pasta Carbonara"
    assert result.recipe.source_type is SourceType.MANUAL
    assert len(result.recipe.ingredients) == 2
    assert result.recipe.instructions == [
        "Kook de pasta.",
        "Meng met de eieren.",
    ]
    assert result.extractor == "manual-text"


def test_supports_english_section_headings() -> None:
    source = """
Tomato Soup

Ingredients:
- 500 g tomatoes
- 1 onion

Instructions:
1. Chop the vegetables.
2. Cook until soft.
"""

    importer = ManualTextRecipeImporter()

    result = importer.import_recipe(source)

    assert result.status is ImportStatus.SUCCESS
    assert result.recipe is not None
    assert result.recipe.title == "Tomato Soup"
    assert len(result.recipe.ingredients) == 2
    assert len(result.recipe.instructions) == 2


def test_supports_bullet_instructions() -> None:
    source = """
Simple Salad

Ingrediënten:
- sla
- tomaat

Bereiding:
- Snijd de tomaat.
- Meng alles.
"""

    importer = ManualTextRecipeImporter()

    result = importer.import_recipe(source)

    assert result.recipe is not None
    assert result.recipe.instructions == [
        "Snijd de tomaat.",
        "Meng alles.",
    ]


def test_returns_failure_for_empty_text() -> None:
    importer = ManualTextRecipeImporter()

    result = importer.import_recipe("   ")

    assert result.status is ImportStatus.FAILED
    assert result.recipe is None
    assert result.warnings[0].code == ("manual_text_empty")


def test_returns_failure_without_recipe_sections() -> None:
    source = """
Dit is alleen een losse tekst zonder recept.
"""

    importer = ManualTextRecipeImporter()

    result = importer.import_recipe(source)

    assert result.status is ImportStatus.FAILED
    assert result.recipe is None
    assert result.warnings[0].code == ("manual_text_recipe_invalid")


def test_manual_text_import_propagates_ingredient_warnings() -> None:
    source = """
Soup

Ingrediënten:
- 1/0 tl zout
- water

Bereiding:
1. Meng alles.
"""

    importer = ManualTextRecipeImporter()

    result = importer.import_recipe(source)

    assert result.status is ImportStatus.PARTIAL
    assert result.recipe is not None
    assert result.warnings
    assert any(warning.code == "quantity_not_parsed" for warning in result.warnings)
