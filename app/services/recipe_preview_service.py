from app.importers.base import RecipeImporter
from app.models.import_result import ImportResult


class RecipePreviewService:
    def __init__(
        self,
        importer: RecipeImporter[str],
    ) -> None:
        self.importer = importer

    def preview(
        self,
        source: str,
    ) -> ImportResult:
        return self.importer.import_recipe(source)
