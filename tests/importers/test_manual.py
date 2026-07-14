from decimal import Decimal

from app.importers.base import RecipeImporter
from app.importers.manual import ManualRecipeImporter
from app.models.import_result import ImportStatus
from app.models.recipe import SourceType


def test_manual_importer_creates_recipe() -> None:
    importer = ManualRecipeImporter()

    data = {
        "title": "  Pasta Carbonara  ",
        "servings": 4,
        "ingredients": [
            {
                "original_text": "400 g spaghetti",
                "name": "spaghetti",
                "quantity": "400",
                "unit": "g",
            },
            {
                "original_text": "4 eggs",
                "name": "eggs",
                "quantity": 4,
                "unit": "pieces",
            },
        ],
        "instructions": [
            "Cook the pasta.",
            "Mix the eggs and cheese.",
        ],
        "tags": ["Pasta", "Quick"],
    }

    result = importer.import_recipe(data)

    assert result.status is ImportStatus.SUCCESS
    assert result.recipe is not None
    assert result.recipe.title == "Pasta Carbonara"
    assert result.recipe.source_type is SourceType.MANUAL
    assert result.recipe.extractor == "manual"
    assert result.recipe.ingredients[0].quantity == Decimal("400")
    assert result.confidence == 1.0


def test_manual_importer_returns_failed_result_for_invalid_data() -> None:
    importer = ManualRecipeImporter()

    result = importer.import_recipe(
        {
            "title": "",
            "ingredients": [],
            "instructions": [],
        }
    )

    assert result.status is ImportStatus.FAILED
    assert result.recipe is None
    assert len(result.warnings) >= 1


def test_manual_importer_does_not_mutate_input() -> None:
    importer = ManualRecipeImporter()

    data = {
        "title": "Pasta",
        "ingredients": [
            {
                "name": "pasta",
            }
        ],
        "instructions": [
            "Cook the pasta.",
        ],
    }

    importer.import_recipe(data)

    assert "source_type" not in data
    assert "extractor" not in data


def test_manual_importer_overrides_source_metadata() -> None:
    importer = ManualRecipeImporter()

    result = importer.import_recipe(
        {
            "title": "Pasta",
            "source_type": "website",
            "extractor": "fake-extractor",
            "ingredients": [
                {
                    "name": "pasta",
                }
            ],
            "instructions": [
                "Cook the pasta.",
            ],
        }
    )

    assert result.recipe is not None
    assert result.recipe.source_type is SourceType.MANUAL
    assert result.recipe.extractor == "manual"


def test_validation_warning_contains_field_location() -> None:
    importer = ManualRecipeImporter()

    result = importer.import_recipe(
        {
            "title": "Pasta",
            "ingredients": [
                {
                    "name": "",
                }
            ],
            "instructions": [
                "Cook the pasta.",
            ],
        }
    )

    assert result.status is ImportStatus.FAILED
    assert any(warning.field == "ingredients.0.name" for warning in result.warnings)


def test_manual_importer_matches_recipe_importer_protocol() -> None:
    importer = ManualRecipeImporter()

    assert isinstance(importer, RecipeImporter)
