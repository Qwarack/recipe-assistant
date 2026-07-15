from pathlib import Path

from app.importers.local_html import LocalHtmlRecipeImporter
from app.models.import_result import ImportStatus


def test_imports_recipe_from_local_html(
    tmp_path: Path,
    load_fixture,
) -> None:
    html_path = tmp_path / "recipe.html"
    html_path.write_text(
        load_fixture("websites/basic_recipe.html"),
        encoding="utf-8",
    )

    importer = LocalHtmlRecipeImporter()

    result = importer.import_recipe(html_path)

    assert result.status is ImportStatus.SUCCESS
    assert result.recipe is not None
    assert result.recipe.title == "Pasta Carbonara"
    assert result.extractor == "local-html"
    assert result.raw_input_reference == str(html_path)


def test_returns_failure_for_missing_html_file(
    tmp_path: Path,
) -> None:
    missing_path = tmp_path / "missing.html"

    importer = LocalHtmlRecipeImporter()

    result = importer.import_recipe(missing_path)

    assert result.status is ImportStatus.FAILED
    assert result.recipe is None
    assert result.warnings[0].code == "html_file_not_found"


def test_rejects_non_html_file(
    tmp_path: Path,
) -> None:
    text_path = tmp_path / "recipe.txt"
    text_path.write_text(
        "Not HTML",
        encoding="utf-8",
    )

    importer = LocalHtmlRecipeImporter()

    result = importer.import_recipe(text_path)

    assert result.status is ImportStatus.FAILED
    assert result.warnings[0].code == ("unsupported_html_file_type")
