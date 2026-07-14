from enum import StrEnum
from typing import Self

from pydantic import BaseModel, Field, model_validator

from app.models.recipe import Recipe


class ImportStatus(StrEnum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class ImportWarning(BaseModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)
    field: str | None = None


class ImportResult(BaseModel):
    status: ImportStatus
    recipe: Recipe | None = None
    warnings: list[ImportWarning] = Field(default_factory=list)
    extractor: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    raw_input_reference: str | None = None

    @model_validator(mode="after")
    def validate_status_and_recipe(self) -> Self:
        if (
            self.status
            in {
                ImportStatus.SUCCESS,
                ImportStatus.PARTIAL,
            }
            and self.recipe is None
        ):
            raise ValueError("Successful and partial imports must contain a recipe")

        if self.status is ImportStatus.FAILED and self.recipe is not None:
            raise ValueError("Failed imports cannot contain a recipe")

        return self
