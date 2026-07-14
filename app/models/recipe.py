from decimal import Decimal
from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


class SourceType(StrEnum):
    WEBSITE = "website"
    MANUAL = "manual"
    MARKDOWN = "markdown"
    IMAGE = "image"
    INSTAGRAM = "instagram"


class Ingredient(BaseModel):
    name: str = Field(min_length=1)
    quantity: Decimal | None = Field(default=None, ge=0)
    unit: str | None = None
    preparation: str | None = None
    optional: bool = False

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()

        if not normalized:
            raise ValueError("Ingredient name cannot be empty")

        return normalized


class Recipe(BaseModel):
    title: str = Field(min_length=1)
    source_type: SourceType
    source_url: str | None = None
    servings: int | None = Field(default=None, gt=0)
    prep_time_minutes: int | None = Field(default=None, ge=0)
    cook_time_minutes: int | None = Field(default=None, ge=0)
    ingredients: list[Ingredient] = Field(min_length=1)
    instructions: list[str] = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)

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

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, values: list[str]) -> list[str]:
        return sorted({value.strip().lower() for value in values if value.strip()})
