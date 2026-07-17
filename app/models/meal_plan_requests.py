from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class AddMealPlanEntryRequest(BaseModel):
    planned_date: date
    recipe_identifier: str = Field(
        min_length=1,
        max_length=255,
    )
    meal_type: Literal["breakfast", "lunch", "dinner"] = Field(
        default="dinner",
        min_length=1,
        max_length=50,
    )
    servings: int = Field(
        default=2,
        ge=1,
        le=50,
    )
    notes: str | None = Field(
        default=None,
        max_length=500,
    )
    plan_name: str | None = Field(
        default=None,
        max_length=255,
    )


class UpdateMealPlanEntryRequest(BaseModel):
    planned_date: date | None = None
    meal_type: Literal["breakfast", "lunch", "dinner"] | None = None
    servings: int | None = Field(
        default=None,
        ge=1,
        le=50,
    )
    notes: str | None = Field(
        default=None,
        max_length=500,
    )
