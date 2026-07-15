from pathlib import Path

from app.importers.website import WebsiteRecipeImporter
from app.models.import_result import ImportStatus
from app.services.markdown_renderer import RecipeMarkdownRenderer
from app.services.recipe_duplicate_detector import RecipeDuplicateDetector
from app.services.recipe_import_service import RecipeImportService
from app.services.recipe_storage import RecipeStorage


class FixtureHttpClient:
    def __init__(self, html: str) -> None:
        self.html = html

    def get_text(self, url: str) -> str:
        return self.html


def test_imports_html_fixture_and_saves_markdown(
    tmp_path: Path,
    load_fixture,
) -> None:
    html = load_fixture("websites/basic_recipe.html")

    importer = WebsiteRecipeImporter(FixtureHttpClient(html))
    renderer = RecipeMarkdownRenderer()
    storage = RecipeStorage(
        recipes_path=tmp_path,
        renderer=renderer,
    )
    duplicate_detector = RecipeDuplicateDetector(recipes_path=tmp_path)

    service = RecipeImportService(
        importer=importer,
        storage=storage,
        duplicate_detector=duplicate_detector,
    )

    result, destination = service.import_and_save("https://example.com/carbonara")

    assert result.status is ImportStatus.SUCCESS
    assert result.recipe is not None
    assert destination is not None
    assert destination.exists()

    markdown = destination.read_text(encoding="utf-8")

    assert result.recipe.title == "Pasta Carbonara"
    assert result.recipe.import_id == result.import_id
    assert result.recipe.content_hash is not None

    assert "# Pasta Carbonara" in markdown
    assert "source_url: https://example.com/carbonara" in markdown
    assert f"id: {result.recipe.id}" in markdown
    assert f"import_id: {result.import_id}" in markdown
    assert f"content_hash: {result.recipe.content_hash}" in markdown
    assert "- 400 g spaghetti" in markdown
    assert "1. Cook the spaghetti." in markdown


def test_importing_same_source_twice_does_not_create_second_file(
    tmp_path: Path,
    load_fixture,
) -> None:
    html = load_fixture("websites/basic_recipe.html")

    importer = WebsiteRecipeImporter(FixtureHttpClient(html))
    renderer = RecipeMarkdownRenderer()
    storage = RecipeStorage(
        recipes_path=tmp_path,
        renderer=renderer,
    )
    duplicate_detector = RecipeDuplicateDetector(recipes_path=tmp_path)

    service = RecipeImportService(
        importer=importer,
        storage=storage,
        duplicate_detector=duplicate_detector,
    )

    first_result, first_destination = service.import_and_save(
        "https://example.com/carbonara"
    )
    second_result, second_destination = service.import_and_save(
        "https://example.com/carbonara"
    )

    assert first_result.status is ImportStatus.SUCCESS
    assert first_destination is not None

    assert second_result.status is ImportStatus.PARTIAL
    assert second_destination == first_destination
    assert any(
        warning.code == "duplicate_source_url" for warning in second_result.warnings
    )

    assert len(list(tmp_path.glob("*.md"))) == 1
