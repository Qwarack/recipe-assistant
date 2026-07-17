from datetime import date

from pydantic import BaseModel, Field


class MealPlanEntryDetail(BaseModel):
    id: int
    planned_date: date
    meal_type: str
    servings: int
    notes: str | None = None

    recipe_identifier: str
    recipe_title: str


class MealPlanDetail(BaseModel):
    id: int
    start_date: date
    end_date: date
    name: str | None = None
    entries: list[MealPlanEntryDetail] = Field(default_factory=list)
