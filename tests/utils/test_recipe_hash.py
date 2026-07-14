from app.models.recipe import Ingredient, Recipe, SourceType
from app.utils.recipe_hash import calculate_recipe_hash


def make_recipe(
    title: str = "Pasta Carbonara",
) -> Recipe:
    return Recipe(
        title=title,
        source_type=SourceType.MANUAL,
        ingredients=[
            Ingredient(
                quantity=200,
                unit="g",
                name="Spaghetti",
            ),
            Ingredient(
                quantity=2,
                name="Eggs",
            ),
        ],
        instructions=[
            "Cook the spaghetti.",
            "Mix with the eggs.",
        ],
    )


def test_same_recipe_content_produces_same_hash() -> None:
    first = make_recipe()
    second = make_recipe()

    assert calculate_recipe_hash(first) == calculate_recipe_hash(second)


def test_hash_ignores_title_case_and_extra_whitespace() -> None:
    first = make_recipe("Pasta Carbonara")
    second = make_recipe("  pasta   carbonara  ")

    assert calculate_recipe_hash(first) == calculate_recipe_hash(second)


def test_different_recipe_content_produces_different_hash() -> None:
    first = make_recipe()
    second = make_recipe().model_copy(
        update={
            "instructions": [
                "Bake the spaghetti.",
                "Mix with the eggs.",
            ]
        }
    )

    assert calculate_recipe_hash(first) != calculate_recipe_hash(second)
