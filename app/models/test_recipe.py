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


def test_website_recipe_requires_source_url() -> None:
    with pytest.raises(ValidationError):
        Recipe(
            title="Pasta",
            source_type=SourceType.WEBSITE,
            ingredients=[
                Ingredient(name="pasta"),
            ],
            instructions=[
                "Cook the pasta.",
            ],
        )


def test_manual_recipe_does_not_require_source_url() -> None:
    recipe = Recipe(
        title="Pasta",
        source_type=SourceType.MANUAL,
        ingredients=[
            Ingredient(name="pasta"),
        ],
        instructions=[
            "Cook the pasta.",
        ],
    )

    assert recipe.source_url is None


def test_total_time_is_calculated_from_prep_and_cook_time() -> None:
    recipe = Recipe(
        title="Pasta",
        source_type=SourceType.MANUAL,
        prep_time_minutes=10,
        cook_time_minutes=20,
        ingredients=[
            Ingredient(name="pasta"),
        ],
        instructions=[
            "Cook the pasta.",
        ],
    )

    assert recipe.total_time_minutes == 30


def test_blank_optional_ingredient_fields_become_none() -> None:
    ingredient = Ingredient(
        name="salt",
        unit="   ",
        preparation=" ",
    )

    assert ingredient.unit is None
    assert ingredient.preparation is None


def test_ingredient_preserves_original_text() -> None:
    ingredient = Ingredient(
        original_text="  2 rode uien, fijngesneden  ",
        name="rode ui",
        quantity=Decimal("2"),
        unit="stuks",
        preparation="fijngesneden",
    )

    assert ingredient.original_text == "2 rode uien, fijngesneden"
    assert ingredient.name == "rode ui"


def test_blank_original_text_becomes_none() -> None:
    ingredient = Ingredient(
        original_text="   ",
        name="salt",
    )

    assert ingredient.original_text is None


def test_ingredient_category_is_normalized() -> None:
    ingredient = Ingredient(
        name="milk",
        category="  dairy  ",
    )

    assert ingredient.category == "dairy"


def test_ingredient_can_be_serialized() -> None:
    ingredient = Ingredient(
        original_text="400 g spaghetti",
        name="spaghetti",
        quantity=Decimal("400"),
        unit="g",
    )

    data = ingredient.model_dump()

    assert data["name"] == "spaghetti"
    assert data["quantity"] == Decimal("400")
    assert data["original_text"] == "400 g spaghetti"
