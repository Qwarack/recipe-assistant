from pathlib import Path
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status

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
from app.api.schemas.imports import AIReparseRequest, WebsiteImportResponse
from app.core.config import get_settings
from app.models.import_session import ImportSession
from app.services.ai_import_orchestrator import (
    AIImportOrchestrator,
    AIImportSourceError,
)
from app.services.import_session_repository import (
    ImportAlreadyProcessingError,
    ImportPermissionError,
    ImportSessionClosedError,
    ImportSessionNotFoundError,
    ImportSessionRepository,
)
from app.services.recipe_import_service import RecipeImportService

router = APIRouter(
    prefix="/imports",
    tags=["imports"],
)

STRONG_DUPLICATE_WARNING_CODES = {
    "duplicate_source_url",
    "duplicate_content",
}


def _response_from_session(
    session: ImportSession,
    *,
    destination: Path | None = None,
) -> WebsiteImportResponse:
    result = session.active_result
    return WebsiteImportResponse(
        import_id=result.import_id,
        created_at=result.created_at,
        status=result.status,
        destination=destination,
        recipe=build_recipe_preview(result),
        warnings=result.warnings,
        metadata=session.metadata,
        ai_enabled=get_settings().ai_enabled,
    )


@router.post(
    "/{import_id}/parse-ai",
    response_model=WebsiteImportResponse,
)
async def parse_import_with_ai(
    import_id: UUID,
    request: AIReparseRequest,
    orchestrator: Annotated[
        AIImportOrchestrator,
        Depends(create_ai_import_orchestrator),
    ],
) -> WebsiteImportResponse:
    if not get_settings().ai_enabled:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Lokale AI-verwerking is uitgeschakeld.",
        )

    try:
        session = await orchestrator.parse_with_ai(
            import_id,
            reason=request.reason,
            discord_user_id=request.discord_user_id,
        )
    except ImportSessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ImportPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except (ImportAlreadyProcessingError, ImportSessionClosedError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AIModelNotFoundError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Het geconfigureerde Gemma-model is nog niet geïnstalleerd op Ollama."
            ),
        ) from exc
    except AITimeoutError as exc:
        raise HTTPException(
            status_code=504,
            detail=("De AI-verwerking duurde te lang. Je kunt het opnieuw proberen."),
        ) from exc
    except (AIInvalidResponseError, AIValidationError) as exc:
        raise HTTPException(
            status_code=422,
            detail=(
                "Gemma gaf geen geldig recept terug. Je kunt opnieuw proberen "
                "of de invoer handmatig aanpassen."
            ),
        ) from exc
    except AIImportSourceError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except (AIUnavailableError, AIServiceError) as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                "Gemma is momenteel niet bereikbaar. Controleer of de "
                "Ollama-container actief is."
            ),
        ) from exc

    return _response_from_session(session)


@router.post(
    "/{import_id}/confirm",
    response_model=WebsiteImportResponse,
)
def confirm_import(
    import_id: UUID,
    service: Annotated[
        RecipeImportService,
        Depends(create_import_service),
    ],
    repository: Annotated[
        ImportSessionRepository,
        Depends(get_import_session_repository),
    ],
    force: bool = False,
    discord_user_id: int | None = None,
) -> WebsiteImportResponse:
    try:
        session = repository.set_owner(import_id, discord_user_id)
    except ImportSessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ImportPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    if session.active_result.recipe is None:
        raise HTTPException(
            status_code=422,
            detail="Deze import bevat nog geen recept dat kan worden opgeslagen.",
        )

    result, destination = service.save_result(
        session.active_result,
        force=force,
    )
    session.active_result = result
    repository.update(session)
    strong_duplicate = any(
        warning.code in STRONG_DUPLICATE_WARNING_CODES for warning in result.warnings
    )

    if destination is not None and (force or not strong_duplicate):
        session = repository.mark_saved(import_id)
    else:
        session = repository.get(import_id)

    return _response_from_session(session, destination=destination)


@router.post(
    "/{import_id}/cancel",
    status_code=status.HTTP_204_NO_CONTENT,
)
def cancel_import(
    import_id: UUID,
    repository: Annotated[
        ImportSessionRepository,
        Depends(get_import_session_repository),
    ],
    discord_user_id: int | None = None,
) -> Response:
    try:
        repository.set_owner(import_id, discord_user_id)
        repository.cancel(import_id)
    except ImportSessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ImportPermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/{import_id}",
    response_model=WebsiteImportResponse,
)
def get_import(
    import_id: UUID,
    repository: Annotated[
        ImportSessionRepository,
        Depends(get_import_session_repository),
    ],
) -> WebsiteImportResponse:
    try:
        session = repository.get(import_id)
    except ImportSessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return _response_from_session(session)
