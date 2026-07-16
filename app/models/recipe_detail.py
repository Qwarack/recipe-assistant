from pydantic import BaseModel, Field, HttpUrl


class RecipeDetail(BaseModel):
    identifier: str
    title: str
    ingredients: list[str]
    instructions: list[str]
    servings: int | None = None
    prep_time_minutes: int | None = None
    cook_time_minutes: int | None = None
    total_time_minutes: int | None = None
    source_url: HttpUrl | None = None
    tags: list[str] = Field(default_factory=list)
    meal_types: list[str] = Field(default_factory=list)
