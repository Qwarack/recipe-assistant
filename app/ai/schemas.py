from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, field_validator

AI_RECIPE_FIELD_NAMES = {
    "title",
    "description",
    "servings",
    "prep_time_minutes",
    "cook_time_minutes",
    "total_time_minutes",
    "ingredients",
    "instructions",
    "cuisine",
    "meal_types",
    "dietary",
    "tags",
    "difficulty",
}


class AIIngredient(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1)
    quantity: Decimal | None = Field(default=None, ge=0)
    unit: str | None = None
    preparation: str | None = None
    optional: bool = False

    @field_validator("name", "unit", "preparation", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value


class AIRecipeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    description: str | None = None
    servings: int | None = Field(default=None, ge=1, le=100)
    prep_time_minutes: int | None = Field(default=None, ge=0, le=1440)
    cook_time_minutes: int | None = Field(default=None, ge=0, le=2880)
    total_time_minutes: int | None = Field(default=None, ge=0, le=4320)
    ingredients: list[AIIngredient] = Field(default_factory=list)
    instructions: list[str] = Field(default_factory=list)
    cuisine: list[str] = Field(default_factory=list)
    meal_types: list[str] = Field(default_factory=list)
    dietary: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    difficulty: str | None = Field(default=None, max_length=50)
    warnings: list[str] = Field(default_factory=list)
    estimated_fields: list[str] = Field(default_factory=list)
    confidence: float | None = Field(default=None, ge=0, le=1)
    confidence_reasons: list[str] = Field(default_factory=list)

    @field_validator("title", "description", "difficulty", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value

    @field_validator(
        "instructions",
        "cuisine",
        "meal_types",
        "dietary",
        "tags",
        "warnings",
        "confidence_reasons",
        mode="before",
    )
    @classmethod
    def normalize_string_lists(cls, value: object) -> object:
        if not isinstance(value, list):
            return value

        return [
            normalized
            for item in value
            if isinstance(item, str) and (normalized := item.strip())
        ]

    @field_validator("estimated_fields")
    @classmethod
    def validate_estimated_fields(cls, values: list[str]) -> list[str]:
        normalized = list(dict.fromkeys(value.strip() for value in values))
        unknown = set(normalized) - AI_RECIPE_FIELD_NAMES

        if unknown:
            names = ", ".join(sorted(unknown))
            raise ValueError(f"Unknown estimated fields: {names}")

        return normalized
