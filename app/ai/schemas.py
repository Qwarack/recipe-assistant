from decimal import Decimal
from typing import Literal, get_args

from pydantic import BaseModel, ConfigDict, Field, field_validator

AIRecipeMealType = Literal[
    "breakfast",
    "lunch",
    "dinner",
    "snack",
    "dessert",
    "drink",
]
AIRecipeDifficulty = Literal["easy", "medium", "hard"]
AIRecipeFieldName = Literal[
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
]

AI_RECIPE_MEAL_TYPES = frozenset(get_args(AIRecipeMealType))
AI_RECIPE_FIELD_NAMES = frozenset(get_args(AIRecipeFieldName))


class AIIngredient(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        min_length=1,
        description="Ingredient name only, without quantity, unit, or preparation.",
    )
    quantity: Decimal | None = Field(
        default=None,
        ge=0,
        description="Numeric quantity from the source; null when absent.",
    )
    unit: str | None = Field(
        default=None,
        description="Short unit without the quantity; null when absent.",
    )
    preparation: str | None = Field(
        default=None,
        description="Preparation note such as chopped or melted; null when absent.",
    )
    optional: bool = Field(
        default=False,
        description="True only when the source marks the ingredient optional.",
    )

    @field_validator("name", "unit", "preparation", mode="before")
    @classmethod
    def normalize_text(cls, value: object) -> object:
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value


class AIRecipeResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(
        default=None,
        description="Recipe title in the source language; null if unrecognized.",
    )
    description: str | None = Field(
        default=None,
        description="Short source-grounded description; null when absent.",
    )
    servings: int | None = Field(
        default=None,
        ge=1,
        le=100,
        description="Number of portions, not free-form serving text.",
    )
    prep_time_minutes: int | None = Field(
        default=None,
        ge=0,
        le=1440,
        description="Active preparation time in whole minutes.",
    )
    cook_time_minutes: int | None = Field(
        default=None,
        ge=0,
        le=2880,
        description="Cooking time in whole minutes.",
    )
    total_time_minutes: int | None = Field(
        default=None,
        ge=0,
        le=4320,
        description="Total elapsed recipe time in whole minutes.",
    )
    ingredients: list[AIIngredient] = Field(
        default_factory=list,
        description="Ingredients in source order, one object per ingredient.",
    )
    instructions: list[str] = Field(
        default_factory=list,
        description="One step per item, without leading numbers or list markers.",
    )
    cuisine: list[str] = Field(
        default_factory=list,
        description="Cuisine labels only, without # prefixes.",
    )
    meal_types: list[AIRecipeMealType] = Field(
        default_factory=list,
        description="Canonical meal types; beverages use drink, not dinner.",
    )
    dietary: list[str] = Field(
        default_factory=list,
        description="Supported dietary labels such as vegetarian or vegan.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Other concise discovery tags; exclude cuisine and dietary.",
    )
    difficulty: AIRecipeDifficulty | None = Field(
        default=None,
        description="Overall recipe difficulty; null when not inferable.",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Material extraction ambiguities requiring user attention.",
    )
    estimated_fields: list[AIRecipeFieldName] = Field(
        default_factory=list,
        description="Top-level field names whose values were inferred.",
    )
    confidence: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Reliability of the complete extraction from 0 to 1.",
    )
    confidence_reasons: list[str] = Field(
        default_factory=list,
        description="Concise causes that reduced confidence.",
    )

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
    def validate_estimated_fields(
        cls,
        values: list[AIRecipeFieldName],
    ) -> list[AIRecipeFieldName]:
        return list(dict.fromkeys(values))
