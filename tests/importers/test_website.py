from decimal import Decimal
from pathlib import Path

from app.importers.website import WebsiteRecipeImporter
from app.models.import_result import ImportStatus, ImportWarning
from app.models.recipe import Ingredient, Recipe, SourceType
from app.services.import_debug_storage import ImportDebugStorage


class FakeHttpClient:
    def __init__(self, html: str) -> None:
        self.html = html

    def get_text(self, url: str) -> str:
        return self.html


class FakeFallback:
    def extract(
        self,
        html: str,
        source_url: str,
    ) -> tuple[Recipe, list[ImportWarning]]:
        return (
            Recipe(
                title="Fallback Recipe",
                source_type=SourceType.WEBSITE,
                source_url=source_url,
                ingredients=[
                    Ingredient(name="pasta"),
                ],
                instructions=[
                    "Cook the pasta.",
                ],
            ),
            [],
        )


class WarningFallback:
    def extract(
        self,
        html: str,
        source_url: str,
    ) -> tuple[Recipe, list[ImportWarning]]:
        recipe = Recipe(
            title="Fallback Soup",
            source_type=SourceType.WEBSITE,
            source_url=source_url,
            ingredients=[
                Ingredient(name="zout"),
            ],
            instructions=[
                "Mix everything.",
            ],
        )
        warnings = [
            ImportWarning(
                code="quantity_not_parsed",
                message="Ingredient quantity could not be parsed",
            )
        ]

        return recipe, warnings


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
    assert result.warnings[0].code == "recipe_extraction_failed"


def test_website_importer_ignores_invalid_json_ld() -> None:
    html = """
    <script type="application/ld+json">
      this is not valid json
    </script>
    """

    importer = WebsiteRecipeImporter(FakeHttpClient(html))

    result = importer.import_recipe("https://example.com/page")

    assert result.status is ImportStatus.FAILED
    assert result.warnings[0].code == "recipe_extraction_failed"


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


def test_website_importer_uses_fallback_without_json_ld() -> None:
    html = "<html><body>No JSON-LD here</body></html>"

    importer = WebsiteRecipeImporter(
        FakeHttpClient(html),
        fallback=FakeFallback(),
    )

    result = importer.import_recipe("https://example.com/pasta")

    assert result.status is ImportStatus.SUCCESS
    assert result.recipe is not None
    assert result.recipe.title == "Fallback Recipe"
    assert result.warnings[0].code == "json_ld_fallback_used"


def test_website_fallback_propagates_ingredient_warnings() -> None:
    importer = WebsiteRecipeImporter(
        FakeHttpClient("<html></html>"),
        fallback=WarningFallback(),
    )

    result = importer.import_recipe("https://example.com/soup")

    assert result.status is ImportStatus.PARTIAL
    assert result.recipe is not None
    assert [warning.code for warning in result.warnings] == [
        "json_ld_fallback_used",
        "quantity_not_parsed",
    ]


class FailingFallback:
    def extract(
        self,
        html: str,
        source_url: str,
    ) -> Recipe:
        raise ValueError("No recipe found")


def test_website_importer_fails_when_all_extractors_fail() -> None:
    html = "<html><body>No recipe data</body></html>"

    importer = WebsiteRecipeImporter(
        FakeHttpClient(html),
        fallback=FailingFallback(),
    )

    result = importer.import_recipe("https://example.com/not-a-recipe")

    assert result.status is ImportStatus.FAILED
    assert result.recipe is None
    assert result.warnings[0].code == "recipe_extraction_failed"


def test_website_importer_saves_html_when_all_extractors_fail(
    tmp_path: Path,
) -> None:
    html = "<html><body>No recipe data</body></html>"

    importer = WebsiteRecipeImporter(
        FakeHttpClient(html),
        fallback=FailingFallback(),
        debug_storage=ImportDebugStorage(tmp_path),
    )

    result = importer.import_recipe("https://example.com/not-a-recipe")

    assert result.status is ImportStatus.FAILED
    assert any(warning.code == "raw_html_saved" for warning in result.warnings)
    assert len(list(tmp_path.glob("*.html"))) == 1


def test_imports_basic_recipe_fixture(
    load_fixture,
) -> None:
    html = load_fixture("websites/basic_recipe.html")

    importer = WebsiteRecipeImporter(FakeHttpClient(html))

    result = importer.import_recipe("https://example.com/carbonara")

    assert result.status is ImportStatus.SUCCESS
    assert result.recipe is not None
    assert result.recipe.title == "Pasta Carbonara"
    assert result.recipe.servings == 4
    assert len(result.recipe.ingredients) == 2
    assert len(result.recipe.instructions) == 2


def test_imports_recipe_from_graph_fixture(
    load_fixture,
) -> None:
    html = load_fixture("websites/recipe_with_graph.html")

    importer = WebsiteRecipeImporter(FakeHttpClient(html))

    result = importer.import_recipe("https://example.com/tomato-soup")

    assert result.status is ImportStatus.SUCCESS
    assert result.recipe is not None
    assert result.recipe.title == "Tomato Soup"
    assert result.recipe.servings == 2


def test_imports_nested_instruction_fixture(
    load_fixture,
) -> None:
    html = load_fixture("websites/nested_instructions.html")

    importer = WebsiteRecipeImporter(FakeHttpClient(html))

    result = importer.import_recipe("https://example.com/bread")

    assert result.recipe is not None
    assert result.recipe.instructions == [
        "Mix flour and water.",
        "Knead the dough.",
        "Bake for 30 minutes.",
    ]


def test_imports_fixture_without_optional_fields(
    load_fixture,
) -> None:
    html = load_fixture("websites/missing_optional_fields.html")

    importer = WebsiteRecipeImporter(FakeHttpClient(html))

    result = importer.import_recipe("https://example.com/simple-salad")

    assert result.status is ImportStatus.SUCCESS
    assert result.recipe is not None
    assert result.recipe.servings is None
    assert result.recipe.total_time_minutes is None


def test_invalid_fixture_fails_cleanly(
    load_fixture,
) -> None:
    html = load_fixture("websites/invalid_recipe.html")

    importer = WebsiteRecipeImporter(
        FakeHttpClient(html),
        fallback=FailingFallback(),
    )

    result = importer.import_recipe("https://example.com/not-a-recipe")

    assert result.status is ImportStatus.FAILED
    assert result.recipe is None
