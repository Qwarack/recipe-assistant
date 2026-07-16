from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.api.imports import build_recipe_preview, create_import_service
from app.api.schemas.imports import WebsiteImportResponse
from app.importers.local_html import LocalHtmlRecipeImporter
from app.importers.manual_text import ManualTextRecipeImporter
from app.importers.markdown import MarkdownRecipeImporter
from app.models.import_result import ImportResult, ImportStatus
from app.services.recipe_import_service import RecipeImportService

router = APIRouter(
    prefix="/imports/upload",
    tags=["imports"],
)


@contextmanager
def _temporary_upload_path(
    *,
    content: bytes,
    filename: str,
) -> Iterator[Path]:
    with TemporaryDirectory(prefix="recipe-upload-") as temporary_directory:
        source = Path(temporary_directory) / Path(filename).name
        source.write_bytes(content)
        yield source


def create_importer_for_extension(
    extension: str,
) -> MarkdownRecipeImporter | ManualTextRecipeImporter | LocalHtmlRecipeImporter:
    if extension == ".md":
        return MarkdownRecipeImporter()

    if extension == ".txt":
        return ManualTextRecipeImporter()

    if extension in {".html", ".htm"}:
        return LocalHtmlRecipeImporter()

    raise HTTPException(
        status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
        detail="Unsupported recipe file type",
    )


def _import_uploaded_recipe(
    *,
    importer: (
        MarkdownRecipeImporter | ManualTextRecipeImporter | LocalHtmlRecipeImporter
    ),
    content: bytes,
    text: str,
    filename: str,
) -> ImportResult:
    if isinstance(importer, ManualTextRecipeImporter):
        return importer.import_recipe(text)

    with _temporary_upload_path(content=content, filename=filename) as source:
        return importer.import_recipe(source)


def _raise_for_failed_import(result: ImportResult) -> None:
    if result.status is not ImportStatus.FAILED:
        return

    raise HTTPException(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        detail={
            "import_id": str(result.import_id),
            "warnings": [warning.model_dump() for warning in result.warnings],
        },
    )


@router.post(
    "/preview",
    response_model=WebsiteImportResponse,
)
async def preview_uploaded_recipe(
    file: Annotated[UploadFile, File(...)],
) -> WebsiteImportResponse:
    filename = file.filename or ""
    extension = Path(filename).suffix.casefold()

    content = await file.read()

    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must use UTF-8 encoding",
        ) from exc

    importer = create_importer_for_extension(extension)
    result = _import_uploaded_recipe(
        importer=importer,
        content=content,
        text=text,
        filename=filename,
    )

    _raise_for_failed_import(result)

    return WebsiteImportResponse(
        import_id=result.import_id,
        created_at=result.created_at,
        status=result.status,
        destination=None,
        recipe=build_recipe_preview(result),
        warnings=result.warnings,
    )


@router.post(
    "",
    response_model=WebsiteImportResponse,
)
async def import_uploaded_recipe(
    file: Annotated[UploadFile, File(...)],
    service: Annotated[
        RecipeImportService,
        Depends(create_import_service),
    ],
    force: bool = False,
) -> WebsiteImportResponse:
    filename = file.filename or ""
    extension = Path(filename).suffix.casefold()
    content = await file.read()

    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file must use UTF-8 encoding",
        ) from exc

    importer = create_importer_for_extension(extension)

    if isinstance(importer, ManualTextRecipeImporter):
        result, destination = service.import_and_save_with(
            text,
            importer=importer,
            force=force,
        )
    else:
        with _temporary_upload_path(content=content, filename=filename) as source:
            result, destination = service.import_and_save_with(
                source,
                importer=importer,
                force=force,
            )

    _raise_for_failed_import(result)

    return WebsiteImportResponse(
        import_id=result.import_id,
        created_at=result.created_at,
        status=result.status,
        destination=destination,
        recipe=build_recipe_preview(result),
        warnings=result.warnings,
    )
