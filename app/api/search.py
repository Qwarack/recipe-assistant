from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.config import get_settings
from app.models.recipe_search import RecipeSearchResult
from app.services.recipe_search_service import (
    RecipeSearchService,
)

router = APIRouter(
    prefix="/recipes",
    tags=["recipes"],
)


def create_recipe_search_service() -> RecipeSearchService:
    settings = get_settings()

    return RecipeSearchService(recipes_path=settings.recipes_path)


@router.get(
    "/search",
    response_model=list[RecipeSearchResult],
)
def search_recipes(
    service: Annotated[
        RecipeSearchService,
        Depends(create_recipe_search_service),
    ],
    query: str = Query(
        min_length=1,
        max_length=100,
    ),
    limit: int = Query(
        default=10,
        ge=1,
        le=25,
    ),
) -> list[RecipeSearchResult]:
    return service.search(
        query,
        limit=limit,
    )
