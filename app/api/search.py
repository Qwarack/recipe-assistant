from collections.abc import Generator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import create_recipe_index_sync_service
from app.core.config import get_settings
from app.database.engine import create_session_factory
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
)
from app.services.recipe_detail_service import (
    RecipeDetailService,
)
from app.services.recipe_index_sync_service import (
    RecipeIndexSyncService,
)

router = APIRouter(
    prefix="/recipes",
    tags=["recipes"],
)


def create_recipe_delete_service(
    index_sync_service: Annotated[
        RecipeIndexSyncService,
        Depends(create_recipe_index_sync_service),
    ],
) -> RecipeDeleteService:
    settings = get_settings()

    return RecipeDeleteService(
        recipes_path=settings.recipes_path,
        index_sync_service=index_sync_service,
    )


def create_recipe_search_service() -> Generator[
    DatabaseRecipeSearchService,
    None,
    None,
]:
    settings = get_settings()

    session_factory = create_session_factory(settings.database_path)

    with session_factory() as session:
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
    deleted = service.delete_by_identifier(identifier)

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Recipe not found",
        )
