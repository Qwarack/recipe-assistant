from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.models.meal_plan import MealPlanDetail
from app.utils.recipe_metadata import normalize_tags


class MealPlanGenerationRequest(BaseModel):
    """Preferences for one generated plan; weekdays use Monday=0 through Sunday=6."""

    start_date: date | None = None
    servings: int = Field(default=2, ge=1, le=50)
    meal_type: Literal["breakfast", "lunch", "dinner"] = "dinner"
    days_to_plan: list[int] | None = None
    max_preparation_time_weekday: int | None = Field(default=None, ge=0)
    max_preparation_time_weekend: int | None = Field(default=None, ge=0)
    vegetarian_days: list[int] = Field(default_factory=list)
    excluded_recipe_identifiers: list[str] = Field(default_factory=list)
    required_tags: list[str] = Field(default_factory=list)
    excluded_tags: list[str] = Field(default_factory=list)
    avoid_recent_days: int = Field(default=21, ge=0, le=3650)
    allow_repeats: bool = False
    preserve_existing_entries: bool = True
    random_seed: int | None = None
    allow_unfilled_slots: bool = False
    enable_leftovers: bool = False
    created_by: str | None = Field(default=None, max_length=64)

    @field_validator("days_to_plan", "vegetarian_days")
    @classmethod
    def validate_weekdays(cls, value: list[int] | None) -> list[int] | None:
        if value is None:
            return None
        if any(day < 0 or day > 6 for day in value):
            raise ValueError("Weekdays must be between 0 and 6")
        return sorted(set(value))

    @field_validator("required_tags", "excluded_tags")
    @classmethod
    def normalize_filter_tags(cls, value: list[str]) -> list[str]:
        return normalize_tags(value)

    @field_validator("excluded_recipe_identifiers")
    @classmethod
    def normalize_identifiers(cls, value: list[str]) -> list[str]:
        return sorted({item.strip() for item in value if item.strip()})


class UnfilledMealPlanSlot(BaseModel):
    planned_date: date
    meal_type: str
    reason: str


class MealPlanSelectionExplanation(BaseModel):
    planned_date: date
    meal_type: str
    recipe_identifier: str
    score: float
    reasons: list[str] = Field(default_factory=list)


class MealPlanGenerationResponse(BaseModel):
    plan: MealPlanDetail
    unfilled_slots: list[UnfilledMealPlanSlot] = Field(default_factory=list)
    selection_explanations: list[MealPlanSelectionExplanation] = Field(
        default_factory=list
    )
    generation_seed: int


class RegenerateMealPlanRequest(BaseModel):
    random_seed: int | None = None


class ActivateMealPlanRequest(BaseModel):
    activated_by: str | None = Field(default=None, max_length=64)


class RerollMealPlanEntryRequest(BaseModel):
    random_seed: int | None = None
