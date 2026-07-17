from collections.abc import Generator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_database_session
from app.core.config import get_settings
from app.database.repositories.recipe_repository import (
    RecipeRepository,
)
from app.models.recipe_detail import RecipeDetail
from app.models.recipe_search import RecipeSearchResult
from app.services.database_recipe_search_service import (
    DatabaseRecipeSearchService,
)
from app.services.recipe_delete_service import (
    RecipeDeleteService,
    RecipeInUseError,
)
from app.services.recipe_detail_service import (
    RecipeDetailService,
)

router = APIRouter(
    prefix="/recipes",
    tags=["recipes"],
)


def create_recipe_delete_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> Generator[
    RecipeDeleteService,
    None,
    None,
]:
    settings = get_settings()
    yield RecipeDeleteService(
        recipes_path=settings.recipes_path,
        session=session,
    )


def create_recipe_search_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> Generator[
    DatabaseRecipeSearchService,
    None,
    None,
]:
    repository = RecipeRepository(session)
    yield DatabaseRecipeSearchService(repository=repository)


@router.get(
    "/search",
    response_model=list[RecipeSearchResult],
)
def search_recipes(
    service: Annotated[
        DatabaseRecipeSearchService,
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


@router.delete(
    "/{identifier}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_recipe(
    identifier: str,
    service: Annotated[
        RecipeDeleteService,
        Depends(create_recipe_delete_service),
    ],
) -> None:
    try:
        deleted = service.delete_by_identifier(identifier)
    except RecipeInUseError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Recipe is used by a meal plan",
        ) from exc

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found",
        )
