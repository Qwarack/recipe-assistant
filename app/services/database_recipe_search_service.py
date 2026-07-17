from app.database.repositories.recipe_repository import (
    RecipeRepository,
)
from app.models.recipe_search import RecipeSearchResult


class DatabaseRecipeSearchService:
    def __init__(
        self,
        repository: RecipeRepository,
    ) -> None:
        self.repository = repository

    def search(
        self,
        query: str,
        *,
        limit: int = 10,
    ) -> list[RecipeSearchResult]:
        records = self.repository.search_by_title(
            query,
            limit=limit,
        )

        return [
            RecipeSearchResult(
                title=record.title,
                path=record.file_path,
                source_url=record.source_url,
            )
            for record in records
        ]
