from app.importers.base import RecipeImporter
from app.models.import_result import ImportResult


def run_import[SourceT](
    importer: RecipeImporter[SourceT],
    source: SourceT,
) -> ImportResult:
    return importer.import_recipe(source)
