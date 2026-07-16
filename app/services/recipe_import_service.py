from pathlib import Path
from typing import TypeVar

from app.importers.base import RecipeImporter
from app.models.import_result import ImportResult, ImportStatus, ImportWarning
from app.services.recipe_duplicate_detector import RecipeDuplicateDetector
from app.services.recipe_storage import (
    RecipeAlreadyExistsError,
    RecipeStorage,
)
from app.utils.recipe_hash import calculate_recipe_hash

SourceT = TypeVar("SourceT")


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
        *,
        force: bool = False,
    ) -> tuple[ImportResult, Path | None]:
        result = self.importer.import_recipe(source)

        return self._save_result(result, force=force)

    def import_and_save_with(
        self,
        source: SourceT,
        *,
        importer: RecipeImporter[SourceT],
        force: bool = False,
    ) -> tuple[ImportResult, Path | None]:
        result = importer.import_recipe(source)

        return self._save_result(result, force=force)

    def _save_result(
        self,
        result: ImportResult,
        *,
        force: bool,
    ) -> tuple[ImportResult, Path | None]:
        if result.recipe is None:
            return result, None

        content_hash = calculate_recipe_hash(result.recipe)

        recipe = result.recipe.model_copy(
            update={
                "import_id": result.import_id,
                "content_hash": content_hash,
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

            if existing_path is not None and not force:
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

        existing_hash_path = self.duplicate_detector.find_by_content_hash(content_hash)

        if existing_hash_path is not None and not force:
            duplicate_warning = ImportWarning(
                code="duplicate_content",
                message=(
                    "A recipe with identical content already exists at "
                    f"{existing_hash_path}."
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

            return duplicate_result, existing_hash_path

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
