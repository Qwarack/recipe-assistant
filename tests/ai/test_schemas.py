from decimal import Decimal

import pytest
from app.ai.schemas import AIRecipeResult
from pydantic import ValidationError


def test_ai_recipe_schema_accepts_valid_recipe() -> None:
    result = AIRecipeResult.model_validate(
        {
            "title": "Soup",
            "servings": 4,
            "ingredients": [{"name": "Water", "quantity": "0.5", "unit": "l"}],
            "instructions": ["Mix."],
        }
    )

    assert result.ingredients[0].quantity == Decimal("0.5")


def test_ai_recipe_schema_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        AIRecipeResult.model_validate({"title": "Soup", "secret": "value"})


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("servings", 0),
        ("servings", 101),
        ("prep_time_minutes", -1),
        ("cook_time_minutes", -1),
        ("total_time_minutes", -1),
    ],
)
def test_ai_recipe_schema_rejects_out_of_range_values(
    field_name: str,
    value: int,
) -> None:
    with pytest.raises(ValidationError):
        AIRecipeResult.model_validate({field_name: value})


def test_ai_recipe_schema_rejects_ingredient_without_name() -> None:
    with pytest.raises(ValidationError):
        AIRecipeResult.model_validate({"ingredients": [{"unit": "g"}]})


def test_ai_recipe_schema_allows_empty_optional_fields() -> None:
    result = AIRecipeResult.model_validate(
        {
            "title": None,
            "ingredients": [],
            "instructions": [],
            "warnings": [],
        }
    )

    assert result.title is None
    assert result.ingredients == []
