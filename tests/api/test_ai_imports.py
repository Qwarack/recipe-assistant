from pathlib import Path
from unittest.mock import AsyncMock

from app.api import ai_imports as ai_imports_api
from app.api.ai_dependencies import (
    create_ai_import_orchestrator,
    get_import_session_repository,
)
from app.api.imports import create_import_service
from app.importers.ai_recipe import AIRecipeImport
from app.main import app
from app.models.import_result import ImportResult, ImportStatus
from app.models.import_session import (
    ImportProcessingStatus,
    ImportSource,
    ParseMethod,
)
from app.models.recipe import Ingredient, Recipe, SourceType
from app.services.import_session_repository import ImportSessionRepository
from fastapi.testclient import TestClient


def _recipe(title: str = "Soup") -> Recipe:
    return Recipe(
        title=title,
        source_type=SourceType.MANUAL,
        ingredients=[Ingredient(name="water")],
        instructions=["Mix."],
    )


def _registered_session(repository: ImportSessionRepository):
    result = ImportResult(status=ImportStatus.SUCCESS, recipe=_recipe())
    session = repository.register(
        result=result,
        source=ImportSource(
            source_type=SourceType.MANUAL,
            raw_text="Soup",
        ),
    )
    return session


def test_parse_ai_endpoint_returns_new_preview_with_metadata() -> None:
    repository = ImportSessionRepository()
    session = _registered_session(repository)
    session.previous_results.append(session.active_result)
    session.active_result = ImportResult(
        import_id=session.import_id,
        created_at=session.created_at,
        status=ImportStatus.SUCCESS,
        recipe=_recipe("AI soup"),
    )
    session.status = ImportProcessingStatus.AWAITING_CONFIRMATION
    session.metadata.parse_method = ParseMethod.AI_REPARSE
    session.metadata.ai_model = "qwen3.5:4b"
    repository.update(session)
    orchestrator = AsyncMock()
    orchestrator.parse_with_ai.return_value = session

    app.dependency_overrides[create_ai_import_orchestrator] = lambda: orchestrator

    try:
        with TestClient(app) as client:
            response = client.post(
                f"/imports/{session.import_id}/parse-ai",
                json={
                    "reason": "user_requested_reparse",
                    "discord_user_id": 123,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["recipe"]["title"] == "AI soup"
    assert response.json()["metadata"]["parse_method"] == "ai_reparse"
    orchestrator.parse_with_ai.assert_awaited_once()


def test_enrich_ai_endpoint_returns_metadata_only_preview() -> None:
    repository = ImportSessionRepository()
    session = _registered_session(repository)
    session.metadata.parse_method = ParseMethod.AI_ENRICHMENT
    session.metadata.ai_model = "qwen3.5:4b"
    session.metadata.estimated_fields = ["tags"]
    repository.update(session)
    orchestrator = AsyncMock()
    orchestrator.enrich_missing_metadata.return_value = session

    app.dependency_overrides[create_ai_import_orchestrator] = lambda: orchestrator

    try:
        with TestClient(app) as client:
            response = client.post(
                f"/imports/{session.import_id}/enrich-ai",
                json={"discord_user_id": 123},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["metadata"]["parse_method"] == "ai_enrichment"
    assert response.json()["metadata"]["estimated_fields"] == ["tags"]
    orchestrator.enrich_missing_metadata.assert_awaited_once_with(
        session.import_id,
        discord_user_id=123,
    )


def test_confirm_endpoint_saves_active_candidate_only_after_confirmation(
    tmp_path: Path,
) -> None:
    repository = ImportSessionRepository()
    session = _registered_session(repository)
    destination = tmp_path / "soup.md"

    class FakeSaveService:
        def __init__(self) -> None:
            self.saved_result = None

        def save_result(self, result, *, force=False):
            self.saved_result = result
            return result, destination

    service = FakeSaveService()
    app.dependency_overrides[get_import_session_repository] = lambda: repository
    app.dependency_overrides[create_import_service] = lambda: service

    try:
        assert service.saved_result is None
        with TestClient(app) as client:
            response = client.post(
                f"/imports/{session.import_id}/confirm",
                params={"discord_user_id": 123},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert service.saved_result.recipe.title == "Soup"
    assert response.json()["destination"] == str(destination)
    assert repository.get(session.import_id).status is ImportProcessingStatus.SAVED


def test_cancel_endpoint_closes_import() -> None:
    repository = ImportSessionRepository()
    session = _registered_session(repository)
    app.dependency_overrides[get_import_session_repository] = lambda: repository

    try:
        with TestClient(app) as client:
            response = client.post(f"/imports/{session.import_id}/cancel")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 204
    assert repository.get(session.import_id).status is ImportProcessingStatus.CANCELLED


def test_response_helper_never_saves_ai_recipe() -> None:
    repository = ImportSessionRepository()
    session = _registered_session(repository)
    imported = AIRecipeImport(
        recipe=_recipe("AI soup"),
        extracted_fields=["title"],
        estimated_fields=[],
        warnings=[],
    )

    assert imported.recipe.title == "AI soup"
    assert session.status is ImportProcessingStatus.AWAITING_CONFIRMATION
    assert ai_imports_api._response_from_session(session).destination is None
