from decimal import Decimal

from app.models.recipe import Ingredient, Recipe, SourceType
from app.services.markdown_renderer import RecipeMarkdownRenderer


def test_renderer_creates_recipe_markdown() -> None:
    recipe = Recipe(
        title="Pasta Carbonara",
        source_type=SourceType.WEBSITE,
        source_url="https://example.com/carbonara",
        servings=4,
        ingredients=[
            Ingredient(
                name="spaghetti",
                quantity=Decimal("400"),
                unit="g",
            ),
            Ingredient(
                name="peterselie",
                quantity=Decimal("1"),
                unit="el",
                optional=True,
            ),
        ],
        instructions=[
            "Cook the pasta.",
            "Mix everything.",
        ],
        tags=["pasta", "quick"],
    )

    markdown = RecipeMarkdownRenderer().render(recipe)

    assert "# Pasta Carbonara" in markdown
    assert "- 400 g spaghetti" in markdown
    assert "- 1 el peterselie _(optioneel)_" in markdown
    assert "1. Cook the pasta." in markdown
    assert "source_type: website" in markdown
    assert "tags:" in markdown
    assert f"id: {recipe.id}" in markdown
