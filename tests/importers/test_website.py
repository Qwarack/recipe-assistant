from decimal import Decimal

from app.importers.website import WebsiteRecipeImporter
from app.models.import_result import ImportStatus
from app.models.recipe import SourceType


class FakeHttpClient:
    def __init__(self, html: str) -> None:
        self.html = html

    def get_text(self, url: str) -> str:
        return self.html


def test_website_importer_extracts_recipe_json_ld() -> None:
    html = """
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Recipe",
          "name": "Pasta Carbonara",
          "recipeYield": "4 servings",
          "recipeIngredient": [
            "400 g spaghetti",
            "4 eggs"
          ],
          "recipeInstructions": [
            {
              "@type": "HowToStep",
              "text": "Cook the pasta."
            },
            {
              "@type": "HowToStep",
              "text": "Mix the eggs and cheese."
            }
          ]
        }
        </script>
      </head>
    </html>
    """

    importer = WebsiteRecipeImporter(FakeHttpClient(html))

    result = importer.import_recipe("https://example.com/carbonara")

    assert result.status is ImportStatus.SUCCESS
    assert result.recipe is not None
    assert result.recipe.title == "Pasta Carbonara"
    assert result.recipe.source_type is SourceType.WEBSITE
    assert result.recipe.servings == 4
    assert len(result.recipe.ingredients) == 2
    assert result.recipe.instructions == [
        "Cook the pasta.",
        "Mix the eggs and cheese.",
    ]


def test_website_importer_supports_graph_json_ld() -> None:
    html = """
    <script type="application/ld+json">
    {
      "@context": "https://schema.org",
      "@graph": [
        {
          "@type": "WebPage",
          "name": "Recipe page"
        },
        {
          "@type": "Recipe",
          "name": "Soup",
          "recipeIngredient": ["water"],
          "recipeInstructions": ["Boil the water."]
        }
      ]
    }
    </script>
    """

    importer = WebsiteRecipeImporter(FakeHttpClient(html))

    result = importer.import_recipe("https://example.com/soup")

    assert result.status is ImportStatus.SUCCESS
    assert result.recipe is not None
    assert result.recipe.title == "Soup"


def test_website_importer_returns_failure_when_recipe_is_missing() -> None:
    html = """
    <script type="application/ld+json">
    {
      "@type": "WebPage",
      "name": "Not a recipe"
    }
    </script>
    """

    importer = WebsiteRecipeImporter(FakeHttpClient(html))

    result = importer.import_recipe("https://example.com/page")

    assert result.status is ImportStatus.FAILED
    assert result.recipe is None
    assert result.warnings[0].code == "recipe_json_ld_not_found"


def test_website_importer_ignores_invalid_json_ld() -> None:
    html = """
    <script type="application/ld+json">
      this is not valid json
    </script>
    """

    importer = WebsiteRecipeImporter(FakeHttpClient(html))

    result = importer.import_recipe("https://example.com/page")

    assert result.status is ImportStatus.FAILED
    assert result.warnings[0].code == "recipe_json_ld_not_found"


def test_website_importer_supports_recipe_type_list() -> None:
    html = """
    <script type="application/ld+json">
    {
      "@type": ["Thing", "Recipe"],
      "name": "Bread",
      "recipeIngredient": ["flour"],
      "recipeInstructions": ["Bake the bread."]
    }
    </script>
    """

    importer = WebsiteRecipeImporter(FakeHttpClient(html))

    result = importer.import_recipe("https://example.com/bread")

    assert result.status is ImportStatus.SUCCESS
    assert result.recipe is not None
    assert result.recipe.title == "Bread"


def test_website_importer_supports_how_to_sections() -> None:
    html = """
    <script type="application/ld+json">
    {
      "@type": "Recipe",
      "name": "Tomato Sauce",
      "recipeIngredient": [
        "2 tomatoes"
      ],
      "recipeInstructions": [
        {
          "@type": "HowToSection",
          "name": "Preparation",
          "itemListElement": [
            {
              "@type": "HowToStep",
              "text": "Chop the tomatoes."
            },
            {
              "@type": "HowToStep",
              "text": "Cook for ten minutes."
            }
          ]
        }
      ]
    }
    </script>
    """

    importer = WebsiteRecipeImporter(FakeHttpClient(html))

    result = importer.import_recipe("https://example.com/tomato-sauce")

    assert result.recipe is not None
    assert result.recipe.instructions == [
        "Preparation",
        "Chop the tomatoes.",
        "Cook for ten minutes.",
    ]


def test_website_importer_supports_string_ingredient() -> None:
    html = """
    <script type="application/ld+json">
    {
      "@type": "Recipe",
      "name": "Salt Water",
      "recipeIngredient": "1 teaspoon salt",
      "recipeInstructions": "Mix the salt into the water."
    }
    </script>
    """

    importer = WebsiteRecipeImporter(FakeHttpClient(html))

    result = importer.import_recipe("https://example.com/salt-water")

    assert result.recipe is not None
    assert len(result.recipe.ingredients) == 1
    assert result.recipe.ingredients[0].original_text == "1 teaspoon salt"
    assert result.recipe.instructions == ["Mix the salt into the water."]


def test_website_importer_reads_publisher_name() -> None:
    html = """
    <script type="application/ld+json">
    {
      "@type": "Recipe",
      "name": "Soup",
      "publisher": {
        "@type": "Organization",
        "name": "Example Recipes"
      },
      "recipeIngredient": ["water"],
      "recipeInstructions": ["Boil the water."]
    }
    </script>
    """

    importer = WebsiteRecipeImporter(FakeHttpClient(html))

    result = importer.import_recipe("https://example.com/soup")

    assert result.recipe is not None
    assert result.recipe.source_name == "Example Recipes"


def test_website_importer_ignores_invalid_ingredient_values() -> None:
    html = """
    <script type="application/ld+json">
    {
      "@type": "Recipe",
      "name": "Soup",
      "recipeIngredient": [
        "water",
        null,
        123,
        "   "
      ],
      "recipeInstructions": ["Boil the water."]
    }
    </script>
    """

    importer = WebsiteRecipeImporter(FakeHttpClient(html))

    result = importer.import_recipe("https://example.com/soup")

    assert result.recipe is not None
    assert len(result.recipe.ingredients) == 1
    assert result.recipe.ingredients[0].name == "water"


def test_website_importer_parses_iso_durations() -> None:
    html = """
    <script type="application/ld+json">
    {
    "@type": "Recipe",
    "name": "Pasta",
    "prepTime": "PT15M",
    "cookTime": "PT30M",
    "totalTime": "PT45M",
    "recipeIngredient": ["pasta"],
    "recipeInstructions": ["Cook the pasta."]
    }
    </script>
    """

    importer = WebsiteRecipeImporter(FakeHttpClient(html))

    result = importer.import_recipe("https://example.com/pasta")

    assert result.recipe is not None
    assert result.recipe.prep_time_minutes == 15
    assert result.recipe.cook_time_minutes == 30
    assert result.recipe.total_time_minutes == 45


def test_total_time_is_calculated_when_json_ld_omits_it() -> None:
    html = """
    <script type="application/ld+json">
    {
    "@type": "Recipe",
    "name": "Pasta",
    "prepTime": "PT10M",
    "cookTime": "PT20M",
    "recipeIngredient": ["pasta"],
    "recipeInstructions": ["Cook the pasta."]
    }
    </script>
    """

    importer = WebsiteRecipeImporter(FakeHttpClient(html))

    result = importer.import_recipe("https://example.com/pasta")

    assert result.recipe is not None
    assert result.recipe.total_time_minutes == 30


def test_invalid_duration_is_ignored() -> None:
    html = """
    <script type="application/ld+json">
    {
    "@type": "Recipe",
    "name": "Pasta",
    "prepTime": "not-a-duration",
    "recipeIngredient": ["pasta"],
    "recipeInstructions": ["Cook the pasta."]
    }
    </script>
    """

    importer = WebsiteRecipeImporter(FakeHttpClient(html))

    result = importer.import_recipe("https://example.com/pasta")

    assert result.status is ImportStatus.SUCCESS
    assert result.recipe is not None
    assert result.recipe.prep_time_minutes is None


def test_duration_with_hours_and_minutes_is_parsed() -> None:
    html = """
    <script type="application/ld+json">
    {
    "@type": "Recipe",
    "name": "Stew",
    "cookTime": "PT1H30M",
    "recipeIngredient": ["vegetables"],
    "recipeInstructions": ["Cook slowly."]
    }
    </script>
    """

    importer = WebsiteRecipeImporter(FakeHttpClient(html))

    result = importer.import_recipe("https://example.com/stew")

    assert result.recipe is not None
    assert result.recipe.cook_time_minutes == 90


def test_website_importer_normalizes_recipe_metadata_as_tags() -> None:
    html = """
    <script type="application/ld+json">
    {
    "@type": "Recipe",
    "name": "Pasta",
    "keywords": "Quick, Pasta, Family",
    "recipeCategory": "Dinner",
    "recipeCuisine": [
        "Italian",
        "European"
    ],
    "recipeIngredient": ["pasta"],
    "recipeInstructions": ["Cook the pasta."]
    }
    </script>
    """

    importer = WebsiteRecipeImporter(FakeHttpClient(html))

    result = importer.import_recipe("https://example.com/pasta")

    assert result.recipe is not None
    assert result.recipe.tags == [
        "dinner",
        "european",
        "family",
        "italian",
        "pasta",
        "quick",
    ]


def test_website_importer_removes_duplicate_tags() -> None:
    html = """
    <script type="application/ld+json">
    {
    "@type": "Recipe",
    "name": "Pasta",
    "keywords": "Pasta, Quick, pasta",
    "recipeCategory": [
        "Dinner",
        "Quick"
    ],
    "recipeCuisine": "Italian, italian",
    "recipeIngredient": ["pasta"],
    "recipeInstructions": ["Cook the pasta."]
    }
    </script>
    """

    importer = WebsiteRecipeImporter(FakeHttpClient(html))

    result = importer.import_recipe("https://example.com/pasta")

    assert result.recipe is not None
    assert result.recipe.tags == [
        "dinner",
        "italian",
        "pasta",
        "quick",
    ]


def test_website_importer_ignores_invalid_tag_values() -> None:
    html = """
    <script type="application/ld+json">
    {
    "@type": "Recipe",
    "name": "Soup",
    "keywords": [
        "Soup",
        null,
        123,
        "   "
    ],
    "recipeCategory": null,
    "recipeIngredient": ["water"],
    "recipeInstructions": ["Boil the water."]
    }
    </script>
    """

    importer = WebsiteRecipeImporter(FakeHttpClient(html))

    result = importer.import_recipe("https://example.com/soup")

    assert result.recipe is not None
    assert result.recipe.tags == ["soup"]


def test_website_importer_parses_simple_ingredients() -> None:
    html = """
    <script type="application/ld+json">
    {
      "@type": "Recipe",
      "name": "Pasta",
      "recipeIngredient": [
        "400 g spaghetti",
        "2 stuks eieren"
      ],
      "recipeInstructions": [
        "Cook the pasta."
      ]
    }
    </script>
    """

    importer = WebsiteRecipeImporter(FakeHttpClient(html))

    result = importer.import_recipe("https://example.com/pasta")

    assert result.recipe is not None

    spaghetti = result.recipe.ingredients[0]
    eggs = result.recipe.ingredients[1]

    assert spaghetti.name == "spaghetti"
    assert spaghetti.quantity == Decimal("400")
    assert spaghetti.unit == "g"

    assert eggs.name == "eieren"
    assert eggs.quantity == Decimal("2")
    assert eggs.unit == "stuks"


def test_website_import_succeeds_for_ingredient_without_quantity() -> None:
    html = """
    <script type="application/ld+json">
    {
      "@type": "Recipe",
      "name": "Pasta",
      "recipeIngredient": [
        "400 g spaghetti",
        "zout naar smaak"
      ],
      "recipeInstructions": [
        "Cook the pasta."
      ]
    }
    </script>
    """

    importer = WebsiteRecipeImporter(FakeHttpClient(html))

    result = importer.import_recipe("https://example.com/pasta")

    assert result.status is ImportStatus.SUCCESS
    assert result.recipe is not None
    assert result.warnings == []


def test_website_import_is_success_when_all_ingredients_parse() -> None:
    html = """
    <script type="application/ld+json">
    {
      "@type": "Recipe",
      "name": "Pasta",
      "recipeIngredient": [
        "400 g spaghetti",
        "2 stuks eieren"
      ],
      "recipeInstructions": [
        "Cook the pasta."
      ]
    }
    </script>
    """

    importer = WebsiteRecipeImporter(FakeHttpClient(html))

    result = importer.import_recipe("https://example.com/pasta")

    assert result.status is ImportStatus.SUCCESS
    assert result.warnings == []


def test_website_import_is_partial_for_invalid_quantity() -> None:
    html = """
    <script type="application/ld+json">
    {
      "@type": "Recipe",
      "name": "Pasta",
      "recipeIngredient": [
        "400 g spaghetti",
        "1/0 tl zout"
      ],
      "recipeInstructions": [
        "Cook the pasta."
      ]
    }
    </script>
    """

    importer = WebsiteRecipeImporter(FakeHttpClient(html))

    result = importer.import_recipe("https://example.com/pasta")

    assert result.status is ImportStatus.PARTIAL
    assert result.recipe is not None
    assert any(warning.code == "quantity_not_parsed" for warning in result.warnings)


def test_website_import_preserves_source_reference() -> None:
    html = """
    <script type="application/ld+json">
    {
      "@type": "Recipe",
      "name": "Soup",
      "recipeIngredient": ["1 l water"],
      "recipeInstructions": ["Boil the water."]
    }
    </script>
    """

    source_url = "https://example.com/soup"
    importer = WebsiteRecipeImporter(FakeHttpClient(html))

    result = importer.import_recipe(source_url)

    assert result.raw_input_reference == source_url


def test_failed_website_import_preserves_source_reference() -> None:
    html = "<html><body>No recipe here</body></html>"

    source_url = "https://example.com/not-a-recipe"
    importer = WebsiteRecipeImporter(FakeHttpClient(html))

    result = importer.import_recipe(source_url)

    assert result.status is ImportStatus.FAILED
    assert result.raw_input_reference == source_url


def test_website_import_sets_imported_at() -> None:
    html = """
    <script type="application/ld+json">
    {
      "@type": "Recipe",
      "name": "Soup",
      "recipeIngredient": ["1 l water"],
      "recipeInstructions": ["Boil the water."]
    }
    </script>
    """

    importer = WebsiteRecipeImporter(FakeHttpClient(html))

    result = importer.import_recipe("https://example.com/soup")

    assert result.recipe is not None
    assert result.recipe.imported_at is not None
    assert result.recipe.imported_at.tzinfo is not None
