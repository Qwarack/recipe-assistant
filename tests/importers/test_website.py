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
