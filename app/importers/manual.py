from collections.abc import Mapping
from typing import Any

from pydantic import ValidationError

from app.models.import_result import (
    ImportResult,
    ImportStatus,
    ImportWarning,
)
from app.models.recipe import Recipe, SourceType


class ManualRecipeImporter:
    extractor_name = "manual"

    def import_recipe(self, data: Mapping[str, Any]) -> ImportResult:
        recipe_data = dict(data)
        recipe_data["source_type"] = SourceType.MANUAL
        recipe_data["extractor"] = self.extractor_name

        try:
            recipe = Recipe.model_validate(recipe_data)
        except ValidationError as exc:
            return ImportResult(
                status=ImportStatus.FAILED,
                extractor=self.extractor_name,
                warnings=self._validation_errors_to_warnings(exc),
            )

        return ImportResult(
            status=ImportStatus.SUCCESS,
            recipe=recipe,
            extractor=self.extractor_name,
            confidence=1.0,
        )

    @staticmethod
    def _validation_errors_to_warnings(
        error: ValidationError,
    ) -> list[ImportWarning]:
        warnings: list[ImportWarning] = []

        for item in error.errors():
            location = ".".join(str(part) for part in item["loc"])

            warnings.append(
                ImportWarning(
                    code=item["type"],
                    message=item["msg"],
                    field=location or None,
                )
            )

        return warnings
