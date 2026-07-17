from datetime import date

from pydantic import BaseModel, Field


class AddMealPlanEntryRequest(BaseModel):
    planned_date: date
    recipe_identifier: str = Field(
        min_length=1,
        max_length=255,
    )
    meal_type: str = Field(
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
