from app.ai.schemas import AIRecipeResult
from app.models.recipe import Ingredient, Recipe, SourceType
from app.services.recipe_enrichment_service import (
    detect_missing_fields,
    merge_enrichment,
)


def _recipe(**updates) -> Recipe:
    data = {
        "title": "Soup",
        "source_type": SourceType.MANUAL,
        "servings": 4,
        "prep_time_minutes": 10,
        "cook_time_minutes": 20,
        "difficulty": "easy",
        "ingredients": [Ingredient(name="water", quantity=1, unit="l")],
        "instructions": ["Mix."],
        "tags": ["soup"],
        "meal_types": ["dinner"],
    }
    data.update(updates)
    return Recipe(**data)


def test_complete_recipe_has_no_missing_fields() -> None:
    report = detect_missing_fields(_recipe())

    assert report.has_missing_fields is False


def test_missing_fields_are_classified() -> None:
    recipe = _recipe(
        servings=None,
        tags=[],
        ingredients=[Ingredient(name="salt")],
    )

    report = detect_missing_fields(recipe)

    assert "servings" in report.enrichable
    assert "tags" in report.enrichable
    assert report.unsafe_to_guess == ["ingredients.0.quantity"]


def test_merge_enrichment_only_fills_missing_values() -> None:
    original = _recipe(
        servings=4,
        prep_time_minutes=None,
        tags=[],
    )
    enrichment = AIRecipeResult(
        servings=8,
        prep_time_minutes=15,
        ingredients=[{"name": "replacement"}],
        instructions=["Replacement instruction."],
        tags=["quick"],
        estimated_fields=["prep_time_minutes"],
        warnings=["Preparation time is estimated.", "Preparation time is estimated."],
    )

    result = merge_enrichment(
        original=original,
        enrichment=enrichment,
    )

    assert result.recipe.servings == 4
    assert result.recipe.prep_time_minutes == 15
    assert result.recipe.tags == ["quick"]
    assert result.recipe.ingredients == original.ingredients
    assert result.recipe.instructions == original.instructions
    assert result.estimated_fields == ["prep_time_minutes"]
    assert result.warnings == ["Preparation time is estimated."]


def test_merge_enrichment_respects_explicit_allowed_fields() -> None:
    original = _recipe(
        servings=None,
        tags=[],
    )
    enrichment = AIRecipeResult(
        servings=6,
        tags=["quick"],
    )

    result = merge_enrichment(
        original=original,
        enrichment=enrichment,
        allowed_fields=["tags"],
    )

    assert result.recipe.servings is None
    assert result.recipe.tags == ["quick"]
