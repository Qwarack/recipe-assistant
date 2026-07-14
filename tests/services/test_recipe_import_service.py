from pathlib import Path

from app.models.import_result import ImportResult, ImportStatus
from app.models.recipe import Ingredient, Recipe, SourceType
from app.services.recipe_import_service import RecipeImportService
from app.services.recipe_storage import RecipeStorage


class FakeImporter:
    extractor_name = "fake"

    def __init__(self, result: ImportResult) -> None:
        self.result = result

    def import_recipe(self, source: str) -> ImportResult:
        return self.result


class FakeRenderer:
    def render(self, recipe: Recipe) -> str:
        return f"# {recipe.title}\nimport_id: {recipe.import_id}\n"


def make_recipe() -> Recipe:
    return Recipe(
        title="Pasta Carbonara",
        source_type=SourceType.WEBSITE,
        source_url="https://example.com/carbonara",
        ingredients=[
            Ingredient(name="pasta"),
        ],
        instructions=[
            "Cook the pasta.",
        ],
    )


def test_import_and_save_creates_markdown_file(
    tmp_path: Path,
) -> None:
    recipe = make_recipe()
    import_result = ImportResult(
        status=ImportStatus.SUCCESS,
        recipe=recipe,
    )

    service = RecipeImportService(
        importer=FakeImporter(import_result),
        storage=RecipeStorage(
            recipes_path=tmp_path,
            renderer=FakeRenderer(),
        ),
    )

    result, destination = service.import_and_save("https://example.com/carbonara")

    assert result.status is ImportStatus.SUCCESS
    assert result.recipe is not None
    assert result.recipe.import_id == result.import_id
    assert result.recipe.import_id is not None

    short_id = str(recipe.id).split("-")[0]
    assert destination == tmp_path / f"pasta-carbonara-{short_id}.md"
    markdown = destination.read_text(encoding="utf-8")
    assert markdown == f"# Pasta Carbonara\nimport_id: {result.import_id}\n"
    assert str(result.import_id) in markdown


def test_failed_import_is_not_saved(
    tmp_path: Path,
) -> None:
    import_result = ImportResult(
        status=ImportStatus.FAILED,
    )

    service = RecipeImportService(
        importer=FakeImporter(import_result),
        storage=RecipeStorage(
            recipes_path=tmp_path,
            renderer=FakeRenderer(),
        ),
    )

    result, destination = service.import_and_save("https://example.com/broken")

    assert result.status is ImportStatus.FAILED
    assert destination is None
    assert list(tmp_path.iterdir()) == []


def test_duplicate_recipe_returns_partial_result(
    tmp_path: Path,
) -> None:
    import_result = ImportResult(
        status=ImportStatus.SUCCESS,
        recipe=make_recipe(),
    )

    service = RecipeImportService(
        importer=FakeImporter(import_result),
        storage=RecipeStorage(
            recipes_path=tmp_path,
            renderer=FakeRenderer(),
        ),
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
    assert second_destination is None
    assert any(
        warning.code == "recipe_already_exists" for warning in second_result.warnings
    )
