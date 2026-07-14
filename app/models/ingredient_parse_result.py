from pydantic import BaseModel, Field

from app.models.recipe import Ingredient


class IngredientParseWarning(BaseModel):
    code: str = Field(min_length=1)
    message: str = Field(min_length=1)


class IngredientParseResult(BaseModel):
    ingredient: Ingredient
    warnings: list[IngredientParseWarning] = Field(default_factory=list)
