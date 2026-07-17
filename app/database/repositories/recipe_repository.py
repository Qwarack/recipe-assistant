from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database.models.recipe import RecipeRecord


class RecipeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def get_by_identifier(
        self,
        identifier: str,
    ) -> RecipeRecord | None:
        statement = select(RecipeRecord).where(RecipeRecord.identifier == identifier)

        return self.session.scalar(statement)

    def add(
        self,
        recipe: RecipeRecord,
    ) -> RecipeRecord:
        self.session.add(recipe)
        self.session.flush()

        return recipe

    def update(
        self,
        recipe: RecipeRecord,
        *,
        title: str,
        file_path: str,
        source_url: str | None,
        content_hash: str | None,
        tags: list[str] | None = None,
        meal_types: list[str] | None = None,
        preparation_time_minutes: int | None = None,
        difficulty: str = "unknown",
        default_servings: int = 2,
        vegetarian: bool | None = None,
        vegan: bool | None = None,
        suitable_for_leftovers: bool = False,
        leftover_servings: int | None = None,
        leftover_days: int = 1,
    ) -> RecipeRecord:
        recipe.title = title
        recipe.file_path = file_path
        recipe.source_url = source_url
        recipe.content_hash = content_hash
        recipe.tags = tags or []
        recipe.meal_types = meal_types or ["dinner"]
        recipe.preparation_time_minutes = preparation_time_minutes
        recipe.difficulty = difficulty
        recipe.default_servings = default_servings
        recipe.vegetarian = vegetarian
        recipe.vegan = vegan
        recipe.suitable_for_leftovers = suitable_for_leftovers
        recipe.leftover_servings = leftover_servings
        recipe.leftover_days = leftover_days

        self.session.flush()

        return recipe

    def list_for_planning(self) -> list[RecipeRecord]:
        statement = select(RecipeRecord).order_by(RecipeRecord.identifier)
        return list(self.session.scalars(statement))

    def mark_planned(
        self,
        recipe: RecipeRecord,
        planned_at: datetime,
    ) -> None:
        recipe.last_planned_at = planned_at

    def delete(
        self,
        recipe: RecipeRecord,
    ) -> None:
        self.session.delete(recipe)
        self.session.flush()

    def delete_by_identifier(
        self,
        identifier: str,
    ) -> bool:
        recipe = self.get_by_identifier(identifier)

        if recipe is None:
            return False

        self.session.delete(recipe)
        self.session.flush()

        return True

    def search_by_title(
        self,
        query: str,
        *,
        limit: int = 10,
    ) -> list[RecipeRecord]:
        normalized_query = query.strip()

        if not normalized_query:
            return []

        statement = (
            select(RecipeRecord)
            .where(RecipeRecord.title.ilike(f"%{normalized_query}%"))
            .order_by(RecipeRecord.title.asc())
            .limit(limit)
        )

        return list(self.session.scalars(statement))
