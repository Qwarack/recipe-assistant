from app.importers import recipe_scrapers_fallback
from app.importers.recipe_scrapers_fallback import (
    RecipeScrapersFallback,
)


class FakeScraper:
    def title(self) -> str:
        return "Pasta Carbonara"

    def site_name(self) -> str:
        return "Example Recipes"

    def yields(self) -> str:
        return "4 servings"

    def prep_time(self) -> int:
        return 10

    def cook_time(self) -> int:
        return 20

    def total_time(self) -> int:
        return 30

    def ingredients(self) -> list[str]:
        return [
            "400 g spaghetti",
            "2 eggs",
        ]

    def instructions_list(self) -> list[str]:
        return [
            "Cook the pasta.",
            "Mix with the eggs.",
        ]


def test_fallback_converts_scraper_output_to_recipe(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        recipe_scrapers_fallback,
        "scrape_html",
        lambda **kwargs: FakeScraper(),
    )

    fallback = RecipeScrapersFallback()

    recipe = fallback.extract(
        html="<html></html>",
        source_url="https://example.com/pasta",
    )

    assert recipe.title == "Pasta Carbonara"
    assert recipe.servings == 4
    assert recipe.extractor == "recipe-scrapers"
    assert len(recipe.ingredients) == 2
    assert len(recipe.instructions) == 2
