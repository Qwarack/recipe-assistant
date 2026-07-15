from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator

from app.utils.recipe_metadata import (
    normalize_meal_types,
    normalize_tags,
)


class SourceType(StrEnum):
    WEBSITE = "website"
    MANUAL = "manual"
    MARKDOWN = "markdown"
    IMAGE = "image"
    INSTAGRAM = "instagram"


class Ingredient(BaseModel):
    original_text: str | None = Field(default=None, min_length=1)
    name: str = Field(min_length=1)
    quantity: Decimal | None = Field(default=None, ge=0)
    unit: str | None = None
    preparation: str | None = None
    category: str | None = None
    optional: bool = False

    @field_validator(
        "original_text",
        "name",
        "unit",
        "preparation",
        "category",
        mode="before",
    )
    @classmethod
    def strip_optional_text(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None

        return value

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str | None) -> str:
        if value is None:
            raise ValueError("Ingredient name cannot be empty")

        return value


class Recipe(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    import_id: UUID | None = None
    content_hash: str | None = None

    title: str = Field(min_length=1)
    source_type: SourceType
    source_url: HttpUrl | None = None
    source_name: str | None = None
    extractor: str | None = None
    imported_at: datetime | None = None

    servings: int | None = Field(default=None, gt=0)
    prep_time_minutes: int | None = Field(default=None, ge=0)
    cook_time_minutes: int | None = Field(default=None, ge=0)
    total_time_minutes: int | None = Field(default=None, ge=0)

    ingredients: list[Ingredient] = Field(min_length=1)
    instructions: list[str] = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)
    meal_types: list[str] = Field(default_factory=list)

    @field_validator("title")
    @classmethod
    def normalize_title(cls, value: str) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError("Recipe title cannot be empty")

        return normalized

    @field_validator("instructions")
    @classmethod
    def normalize_instructions(cls, values: list[str]) -> list[str]:
        normalized = [value.strip() for value in values if value.strip()]

        if not normalized:
            raise ValueError("Recipe must contain at least one instruction")

        return normalized

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_recipe_tags(
        cls,
        value: object,
    ) -> list[str]:
        if value is None:
            return []

        if isinstance(value, str):
            return normalize_tags([value])

        if isinstance(value, list):
            string_values = [item for item in value if isinstance(item, str)]
            return normalize_tags(string_values)

        raise ValueError("Tags must be a string or list of strings.")

    @field_validator("meal_types", mode="before")
    @classmethod
    def normalize_recipe_meal_types(
        cls,
        value: object,
    ) -> list[str]:
        if value is None:
            return []

        if isinstance(value, str):
            return normalize_meal_types([value])

        if isinstance(value, list):
            string_values = [item for item in value if isinstance(item, str)]
            return normalize_meal_types(string_values)

        raise ValueError("Meal types must be a string or list of strings.")

    @model_validator(mode="after")
    def validate_source(self) -> "Recipe":
        if (
            self.source_type
            in {
                SourceType.WEBSITE,
                SourceType.INSTAGRAM,
            }
            and self.source_url is None
        ):
            raise ValueError(
                "A source URL is required for website and Instagram recipes"
            )

        return self

    @model_validator(mode="after")
    def calculate_total_time(self) -> "Recipe":
        if self.total_time_minutes is None:
            known_times = [
                value
                for value in (
                    self.prep_time_minutes,
                    self.cook_time_minutes,
                )
                if value is not None
            ]

            if known_times:
                self.total_time_minutes = sum(known_times)

        return self

    @field_validator("source_name", "extractor", mode="before")
    @classmethod
    def normalize_optional_recipe_text(cls, value: object) -> object:
        if isinstance(value, str):
            stripped = value.strip()
            return stripped or None

        return value

    @field_validator("imported_at")
    @classmethod
    def validate_imported_at(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None

        if value.tzinfo is None:
            raise ValueError("imported_at must include timezone information")

        return value.astimezone(UTC)
