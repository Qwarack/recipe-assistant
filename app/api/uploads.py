from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status

from app.ai.exceptions import (
    AIInvalidResponseError,
    AIModelNotFoundError,
    AIServiceError,
    AITimeoutError,
    AIUnavailableError,
    AIValidationError,
)
from app.api.ai_dependencies import (
    create_ai_import_orchestrator,
    get_import_session_repository,
)
from app.api.imports import build_recipe_preview, create_import_service
from app.api.schemas.imports import WebsiteImportResponse
from app.core.config import get_settings
from app.importers.local_html import LocalHtmlRecipeImporter
from app.importers.manual_text import ManualTextRecipeImporter
from app.importers.markdown import MarkdownRecipeImporter
from app.models.import_result import ImportResult, ImportStatus
from app.models.import_session import (
    AIParseReason,
    ImportSession,
    ImportSource,
)
from app.models.recipe import SourceType
from app.services.ai_import_orchestrator import (
    AIImportOrchestrator,
    AIImportSourceError,
)
from app.services.image_processing import (
    ALLOWED_IMAGE_EXTENSIONS,
    ImageValidationError,
    TemporaryImageStorage,
    normalize_recipe_image,
)
from app.services.import_session_repository import ImportSessionRepository
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


def _register_upload_session(
    *,
    repository: ImportSessionRepository,
    result: ImportResult,
    extension: str,
    text: str,
    filename: str,
    content_type: str | None,
) -> ImportSession:
    source_type = SourceType.MARKDOWN if extension == ".md" else SourceType.MANUAL
    return repository.register(
        result=result,
        source=ImportSource(
            source_type=source_type,
            raw_text=text,
            original_filename=filename,
            content_type=content_type,
        ),
    )


@router.post(
    "/preview",
    response_model=WebsiteImportResponse,
)
async def preview_uploaded_recipe(
    file: Annotated[UploadFile, File(...)],
    orchestrator: Annotated[
        AIImportOrchestrator,
        Depends(create_ai_import_orchestrator),
    ],
    repository: Annotated[
        ImportSessionRepository,
        Depends(get_import_session_repository),
    ],
) -> WebsiteImportResponse:
    filename = file.filename or ""
    extension = Path(filename).suffix.casefold()

    content = await file.read()

    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is empty",
        )

    if extension in ALLOWED_IMAGE_EXTENSIONS:
        return await _preview_image_recipe(
            content=content,
            filename=filename,
            content_type=file.content_type,
            orchestrator=orchestrator,
            repository=repository,
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
    session = _register_upload_session(
        repository=repository,
        result=result,
        extension=extension,
        text=text,
        filename=filename,
        content_type=file.content_type,
    )

    _raise_for_failed_import(result)

    return WebsiteImportResponse(
        import_id=result.import_id,
        created_at=result.created_at,
        status=result.status,
        destination=None,
        recipe=build_recipe_preview(result),
        warnings=result.warnings,
        metadata=session.metadata,
        ai_enabled=get_settings().ai_enabled,
    )


async def _preview_image_recipe(
    *,
    content: bytes,
    filename: str,
    content_type: str | None,
    orchestrator: AIImportOrchestrator,
    repository: ImportSessionRepository,
) -> WebsiteImportResponse:
    settings = get_settings()

    if not settings.ai_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Afbeeldingsimport vereist dat lokale AI is ingeschakeld.",
        )

    try:
        normalized = normalize_recipe_image(
            content=content,
            filename=filename,
            content_type=content_type,
            max_bytes=settings.max_image_upload_bytes,
            max_dimension=settings.max_image_dimension,
        )
    except ImageValidationError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    import_id = uuid4()
    temporary_path = TemporaryImageStorage(settings.imports_path).save(
        import_id=import_id,
        image=normalized,
    )
    pending_result = ImportResult(
        import_id=import_id,
        status=ImportStatus.FAILED,
        warnings=[],
        extractor="ollama-vision",
        raw_input_reference=filename,
    )
    repository.register(
        result=pending_result,
        source=ImportSource(
            source_type=SourceType.IMAGE,
            temporary_file_path=temporary_path,
            original_filename=filename,
            content_type=normalized.content_type,
        ),
    )

    try:
        session = await orchestrator.parse_with_ai(
            import_id,
            reason=AIParseReason.IMAGE_INPUT,
        )
    except AIServiceError as exc:
        _raise_image_ai_error(exc, import_id=import_id)

    result = session.active_result
    return WebsiteImportResponse(
        import_id=result.import_id,
        created_at=result.created_at,
        status=result.status,
        destination=None,
        recipe=build_recipe_preview(result),
        warnings=result.warnings,
        metadata=session.metadata,
        ai_enabled=True,
    )


def _raise_image_ai_error(exc: AIServiceError, *, import_id: UUID) -> None:
    detail: dict[str, str] = {
        "import_id": str(import_id),
        "message": (
            "Gemma is momenteel niet bereikbaar. Controleer of de "
            "Ollama-container actief is."
        ),
    }
    status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    if isinstance(exc, AIModelNotFoundError):
        detail["message"] = (
            "Het geconfigureerde Gemma-model is nog niet geïnstalleerd op Ollama."
        )
    elif isinstance(exc, AITimeoutError):
        status_code = status.HTTP_504_GATEWAY_TIMEOUT
        detail["message"] = (
            "De AI-verwerking duurde te lang. Je kunt het opnieuw proberen."
        )
    elif isinstance(
        exc,
        AIInvalidResponseError | AIValidationError | AIImportSourceError,
    ):
        status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
        detail["message"] = (
            "Er kon geen duidelijk recept in deze afbeelding worden herkend."
        )
    elif not isinstance(exc, AIUnavailableError):
        status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
        detail["message"] = "De afbeelding kon niet met Gemma worden verwerkt."

    raise HTTPException(status_code=status_code, detail=detail) from exc


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
