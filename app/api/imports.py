from collections.abc import Generator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.schemas.imports import (
    WebsiteImportRequest,
    WebsiteImportResponse,
)
from app.core.config import get_settings
from app.core.http_client import SafeHttpClient
from app.importers.website import WebsiteRecipeImporter
from app.models.import_result import ImportStatus
from app.services.markdown_renderer import RecipeMarkdownRenderer
from app.services.recipe_duplicate_detector import RecipeDuplicateDetector
from app.services.recipe_import_service import RecipeImportService
from app.services.recipe_storage import RecipeStorage

router = APIRouter(
    prefix="/imports",
    tags=["imports"],
)


def get_http_client() -> Generator[SafeHttpClient, None, None]:
    with SafeHttpClient() as client:
        yield client


def create_import_service(
    http_client: Annotated[
        SafeHttpClient,
        Depends(get_http_client),
    ],
) -> RecipeImportService:
    settings = get_settings()

    importer = WebsiteRecipeImporter(http_client)
    renderer = RecipeMarkdownRenderer()
    storage = RecipeStorage(
        recipes_path=settings.recipes_path,
        renderer=renderer,
    )
    duplicate_detector = RecipeDuplicateDetector(recipes_path=settings.recipes_path)

    return RecipeImportService(
        importer=importer,
        storage=storage,
        duplicate_detector=duplicate_detector,
    )


@router.post(
    "/website",
    response_model=WebsiteImportResponse,
    status_code=status.HTTP_201_CREATED,
)
def import_website_recipe(
    request: WebsiteImportRequest,
    service: Annotated[
        RecipeImportService,
        Depends(create_import_service),
    ],
) -> WebsiteImportResponse:
    result, destination = service.import_and_save(str(request.url), force=request.force)

    if result.status is ImportStatus.FAILED:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "import_id": str(result.import_id),
                "warnings": [warning.model_dump() for warning in result.warnings],
            },
        )

    return WebsiteImportResponse(
        import_id=result.import_id,
        status=result.status,
        destination=destination,
        warnings=result.warnings,
    )
