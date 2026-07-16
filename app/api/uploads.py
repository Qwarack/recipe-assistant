from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated

from fastapi import APIRouter, File, HTTPException, UploadFile, status

from app.api.imports import build_recipe_preview
from app.api.schemas.imports import WebsiteImportResponse
from app.importers.local_html import LocalHtmlRecipeImporter
from app.importers.manual_text import ManualTextRecipeImporter
from app.importers.markdown import MarkdownRecipeImporter
from app.models.import_result import ImportResult, ImportStatus

router = APIRouter(
    prefix="/imports/upload",
    tags=["imports"],
)


def _import_path_recipe(
    *,
    importer: MarkdownRecipeImporter | LocalHtmlRecipeImporter,
    content: bytes,
    filename: str,
) -> ImportResult:
    with TemporaryDirectory(prefix="recipe-upload-") as temporary_directory:
        source = Path(temporary_directory) / Path(filename).name
        source.write_bytes(content)
        return importer.import_recipe(source)


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

    if extension == ".md":
        result = _import_path_recipe(
            importer=MarkdownRecipeImporter(),
            content=content,
            filename=filename,
        )
    elif extension == ".txt":
        result = ManualTextRecipeImporter().import_recipe(text)
    elif extension in {".html", ".htm"}:
        result = _import_path_recipe(
            importer=LocalHtmlRecipeImporter(),
            content=content,
            filename=filename,
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported recipe file type",
        )

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
        created_at=result.created_at,
        status=result.status,
        destination=None,
        recipe=build_recipe_preview(result),
        warnings=result.warnings,
    )
