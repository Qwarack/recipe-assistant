from pathlib import Path

from app.database.repositories.recipe_repository import (
    RecipeRepository,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


class RecipeInUseError(Exception):
    """Raised when a planned recipe cannot be deleted."""


class RecipeDeleteService:
    def __init__(
        self,
        recipes_path: Path,
        session: Session | None = None,
    ) -> None:
        self.recipes_path = recipes_path
        self.session = session
        self.repository = RecipeRepository(session) if session is not None else None

    def delete_by_identifier(
        self,
        identifier: str,
    ) -> bool:
        safe_identifier = Path(identifier).name
        recipe_path = self.recipes_path / f"{safe_identifier}.md"

        if not recipe_path.is_file():
            return False

        if self.repository is not None and self.session is not None:
            try:
                self.repository.delete_by_identifier(safe_identifier)
                self.session.commit()
            except IntegrityError as exc:
                self.session.rollback()
                raise RecipeInUseError("Recipe is used by a meal plan") from exc

        recipe_path.unlink()

        return True
