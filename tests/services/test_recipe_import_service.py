from pathlib import Path

from app.models.import_result import ImportResult, ImportStatus
from app.models.recipe import Ingredient, Recipe, SourceType
from app.services.recipe_duplicate_detector import RecipeDuplicateDetector
from app.services.recipe_import_service import RecipeImportService
from app.services.recipe_storage import RecipeStorage
from app.utils.recipe_hash import calculate_recipe_hash


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
        source_url="https://example.com/pasta",
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
        duplicate_detector=RecipeDuplicateDetector(tmp_path),
    )

    result, destination = service.import_and_save("https://example.com/pasta")

    assert result.status is ImportStatus.SUCCESS
    assert result.recipe is not None
    assert result.recipe.import_id == result.import_id
    assert result.recipe.import_id is not None

    short_id = str(recipe.id).split("-")[0]
    assert destination == tmp_path / f"pasta-carbonara-{short_id}.md"
    markdown = destination.read_text(encoding="utf-8")
    assert markdown == f"# Pasta Carbonara\nimport_id: {result.import_id}\n"
    assert str(result.import_id) in markdown
    assert result.recipe.content_hash is not None
    assert len(result.recipe.content_hash) == 64


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
        duplicate_detector=RecipeDuplicateDetector(tmp_path),
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
        duplicate_detector=RecipeDuplicateDetector(tmp_path),
    )

    first_result, first_destination = service.import_and_save(
        "https://example.com/pasta"
    )
    second_result, second_destination = service.import_and_save(
        "https://example.com/pasta"
    )

    assert first_result.status is ImportStatus.SUCCESS
    assert first_destination is not None

    assert second_result.status is ImportStatus.PARTIAL
    assert second_destination is None
    assert any(
        warning.code == "recipe_already_exists" for warning in second_result.warnings
    )


def test_import_does_not_save_duplicate_source_url(
    tmp_path: Path,
) -> None:
    existing_path = tmp_path / "existing-pasta.md"
    existing_path.write_text(
        """---
title: Pasta
source_url: https://example.com/pasta
---

# Pasta
""",
        encoding="utf-8",
    )

    recipe = make_recipe()
    import_result = ImportResult(
        status=ImportStatus.SUCCESS,
        recipe=recipe,
    )

    importer = FakeImporter(import_result)
    storage = RecipeStorage(
        recipes_path=tmp_path,
        renderer=FakeRenderer(),
    )
    duplicate_detector = RecipeDuplicateDetector(tmp_path)

    service = RecipeImportService(
        importer=importer,
        storage=storage,
        duplicate_detector=duplicate_detector,
    )

    result, destination = service.import_and_save("https://example.com/pasta")

    assert result.status is ImportStatus.PARTIAL
    assert destination == existing_path
    assert len(result.warnings) == 1
    assert result.warnings[0].code == "duplicate_source_url"

    markdown_files = list(tmp_path.glob("*.md"))

    assert markdown_files == [existing_path]


def test_import_saves_recipe_with_duplicate_title_warning(
    tmp_path: Path,
) -> None:
    existing_path = tmp_path / "existing-pasta.md"
    existing_path.write_text(
        """---
title: Pasta Carbonara
source_url: https://example.com/old-pasta
---

# Pasta Carbonara
""",
        encoding="utf-8",
    )

    recipe = make_recipe().model_copy(
        update={
            "source_url": "https://example.com/new-pasta",
        }
    )

    import_result = ImportResult(
        status=ImportStatus.SUCCESS,
        recipe=recipe,
    )

    importer = FakeImporter(import_result)
    storage = RecipeStorage(
        recipes_path=tmp_path,
        renderer=FakeRenderer(),
    )
    duplicate_detector = RecipeDuplicateDetector(tmp_path)

    service = RecipeImportService(
        importer=importer,
        storage=storage,
        duplicate_detector=duplicate_detector,
    )

    result, destination = service.import_and_save("https://example.com/new-pasta")

    assert result.status is ImportStatus.PARTIAL
    assert destination is not None
    assert destination.exists()

    assert len(result.warnings) == 1
    assert result.warnings[0].code == "duplicate_title"

    markdown_files = list(tmp_path.glob("*.md"))

    assert len(markdown_files) == 2


def test_import_does_not_save_duplicate_content(
    tmp_path: Path,
) -> None:
    recipe = make_recipe().model_copy(
        update={
            "source_url": "https://example.com/new-source",
        }
    )

    content_hash = calculate_recipe_hash(recipe)

    existing_path = tmp_path / "existing-pasta.md"
    existing_path.write_text(
        f"""---
title: Existing Pasta
source_url: https://example.com/old-source
content_hash: {content_hash}
---

# Existing Pasta
""",
        encoding="utf-8",
    )

    import_result = ImportResult(
        status=ImportStatus.SUCCESS,
        recipe=recipe,
    )

    importer = FakeImporter(import_result)
    storage = RecipeStorage(
        recipes_path=tmp_path,
        renderer=FakeRenderer(),
    )
    duplicate_detector = RecipeDuplicateDetector(tmp_path)

    service = RecipeImportService(
        importer=importer,
        storage=storage,
        duplicate_detector=duplicate_detector,
    )

    result, destination = service.import_and_save("https://example.com/new-source")

    assert result.status is ImportStatus.PARTIAL
    assert destination == existing_path
    assert result.warnings[-1].code == "duplicate_content"

    markdown_files = list(tmp_path.glob("*.md"))

    assert markdown_files == [existing_path]


def test_force_import_saves_duplicate_content(
    tmp_path: Path,
) -> None:
    recipe = make_recipe().model_copy(
        update={
            "source_url": "https://example.com/new-source",
        }
    )

    content_hash = calculate_recipe_hash(recipe)

    existing_path = tmp_path / "existing-pasta.md"
    existing_path.write_text(
        f"""---
title: Pasta Carbonara
source_url: https://example.com/old-source
content_hash: {content_hash}
---

# Pasta Carbonara
""",
        encoding="utf-8",
    )

    import_result = ImportResult(
        status=ImportStatus.SUCCESS,
        recipe=recipe,
    )

    importer = FakeImporter(import_result)
    storage = RecipeStorage(
        recipes_path=tmp_path,
        renderer=FakeRenderer(),
    )
    duplicate_detector = RecipeDuplicateDetector(tmp_path)

    service = RecipeImportService(
        importer=importer,
        storage=storage,
        duplicate_detector=duplicate_detector,
    )

    result, destination = service.import_and_save(
        "https://example.com/new-source",
        force=True,
    )

    assert destination is not None
    assert destination != existing_path
    assert destination.exists()

    markdown_files = list(tmp_path.glob("*.md"))

    assert len(markdown_files) == 2
