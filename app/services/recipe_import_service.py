from pathlib import Path

from app.importers.base import RecipeImporter
from app.models.import_result import ImportResult, ImportStatus, ImportWarning
from app.services.recipe_storage import (
    RecipeAlreadyExistsError,
    RecipeStorage,
)


class RecipeImportService:
    def __init__(
        self,
        importer: RecipeImporter[str],
        storage: RecipeStorage,
    ) -> None:
        self.importer = importer
        self.storage = storage

    def import_and_save(
        self,
        source: str,
    ) -> tuple[ImportResult, Path | None]:
        result = self.importer.import_recipe(source)

        if result.recipe is None:
            return result, None

        try:
            destination = self.storage.save(result.recipe)
        except RecipeAlreadyExistsError as exc:
            duplicate_warning = ImportWarning(
                code="recipe_already_exists",
                message=str(exc),
            )

            updated_result = result.model_copy(
                update={
                    "status": ImportStatus.PARTIAL,
                    "warnings": [
                        *result.warnings,
                        duplicate_warning,
                    ],
                }
            )

            return updated_result, None

        return result, destination
