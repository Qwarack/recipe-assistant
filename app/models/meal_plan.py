from datetime import date, datetime

from pydantic import BaseModel, Field


class MealPlanEntryDetail(BaseModel):
    id: int
    planned_date: date
    meal_type: str
    servings: int
    notes: str | None = None

    recipe_identifier: str
    recipe_title: str
    preparation_time_minutes: int | None = None
    source: str = "manual"
    source_entry_id: int | None = None


class MealPlanDetail(BaseModel):
    id: int
    start_date: date
    end_date: date
    name: str | None = None
    status: str = "active"
    generation_seed: int | None = None
    generated_at: datetime | None = None
    entries: list[MealPlanEntryDetail] = Field(default_factory=list)
