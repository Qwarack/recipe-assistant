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
    ) -> RecipeRecord:
        recipe.title = title
        recipe.file_path = file_path
        recipe.source_url = source_url
        recipe.content_hash = content_hash

        self.session.flush()

        return recipe

    def delete(
        self,
        recipe: RecipeRecord,
    ) -> None:
        self.session.delete(recipe)
        self.session.flush()
