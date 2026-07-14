from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.models.recipe import Ingredient, Recipe, SourceType


def test_recipe_can_be_created() -> None:
    recipe = Recipe(
        title="  Pasta Carbonara  ",
        source_type=SourceType.WEBSITE,
        source_url="https://example.com/carbonara",
        servings=4,
        prep_time_minutes=10,
        cook_time_minutes=20,
        ingredients=[
            Ingredient(
                name="  spaghetti  ",
                quantity=Decimal("400"),
                unit="g",
            ),
            Ingredient(
                name="eggs",
                quantity=Decimal("4"),
                unit="pieces",
            ),
        ],
        instructions=[
            "  Cook the pasta.  ",
            "Mix the eggs and cheese.",
        ],
        tags=["Pasta", "quick", "pasta"],
    )

    assert recipe.title == "Pasta Carbonara"
    assert recipe.ingredients[0].name == "spaghetti"
    assert recipe.instructions[0] == "Cook the pasta."
    assert recipe.tags == ["pasta", "quick"]


def test_recipe_requires_at_least_one_ingredient() -> None:
    with pytest.raises(ValidationError):
        Recipe(
            title="Empty recipe",
            source_type=SourceType.MANUAL,
            ingredients=[],
            instructions=["Do something."],
        )


def test_ingredient_quantity_cannot_be_negative() -> None:
    with pytest.raises(ValidationError):
        Ingredient(
            name="flour",
            quantity=Decimal("-100"),
            unit="g",
        )
