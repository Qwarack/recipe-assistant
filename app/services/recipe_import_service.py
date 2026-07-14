from pathlib import Path

from app.importers.base import RecipeImporter
from app.models.import_result import ImportResult, ImportStatus, ImportWarning
from app.services.recipe_duplicate_detector import RecipeDuplicateDetector
from app.services.recipe_storage import (
    RecipeAlreadyExistsError,
    RecipeStorage,
)
from app.utils.recipe_hash import calculate_recipe_hash


class RecipeImportService:
    def __init__(
        self,
        importer: RecipeImporter[str],
        storage: RecipeStorage,
        duplicate_detector: RecipeDuplicateDetector,
    ) -> None:
        self.importer = importer
        self.storage = storage
        self.duplicate_detector = duplicate_detector

    def import_and_save(
        self,
        source: str,
    ) -> tuple[ImportResult, Path | None]:
        result = self.importer.import_recipe(source)

        if result.recipe is None:
            return result, None

        recipe = result.recipe.model_copy(
            update={
                "import_id": result.import_id,
                "content_hash": calculate_recipe_hash(result.recipe),
            }
        )

        result = result.model_copy(
            update={
                "recipe": recipe,
            }
        )

        if recipe.source_url is not None:
            existing_path = self.duplicate_detector.find_by_source_url(
                str(recipe.source_url)
            )

            if existing_path is not None:
                duplicate_warning = ImportWarning(
                    code="duplicate_source_url",
                    message=(
                        "A recipe with this source URL already exists at "
                        f"{existing_path}."
                    ),
                )

                duplicate_result = result.model_copy(
                    update={
                        "status": ImportStatus.PARTIAL,
                        "warnings": [
                            *result.warnings,
                            duplicate_warning,
                        ],
                    }
                )

                return duplicate_result, existing_path

        existing_title_path = self.duplicate_detector.find_by_title(recipe.title)

        if existing_title_path is not None:
            title_warning = ImportWarning(
                code="duplicate_title",
                message=(
                    "A recipe with a similar title already exists at "
                    f"{existing_title_path}."
                ),
            )

            result = result.model_copy(
                update={
                    "status": ImportStatus.PARTIAL,
                    "warnings": [
                        *result.warnings,
                        title_warning,
                    ],
                }
            )

        try:
            destination = self.storage.save(recipe)
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
