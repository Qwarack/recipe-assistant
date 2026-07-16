from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.config import get_settings
from app.models.recipe_detail import RecipeDetail
from app.models.recipe_search import RecipeSearchResult
from app.services.recipe_detail_service import (
    RecipeDetailService,
)
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


def create_recipe_detail_service() -> RecipeDetailService:
    settings = get_settings()

    return RecipeDetailService(recipes_path=settings.recipes_path)


@router.get(
    "/{identifier}",
    response_model=RecipeDetail,
)
def get_recipe(
    identifier: str,
    service: Annotated[
        RecipeDetailService,
        Depends(create_recipe_detail_service),
    ],
) -> RecipeDetail:
    recipe = service.get_by_identifier(identifier)

    if recipe is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found",
        )

    return recipe
