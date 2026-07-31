from io import BytesIO
from uuid import UUID

from app.api.ai_dependencies import (
    create_ai_import_orchestrator,
    get_import_session_repository,
)
from app.api.imports import create_import_service
from app.core.config import Settings
from app.importers.manual_text import ManualTextRecipeImporter
from app.main import app
from app.models.import_result import ImportResult, ImportStatus
from app.models.import_session import (
    ImportProcessingStatus,
    ParseMethod,
)
from app.models.recipe import Ingredient, Recipe, SourceType
from app.services.import_session_repository import ImportSessionRepository
from app.services.markdown_renderer import RecipeMarkdownRenderer
from app.services.recipe_duplicate_detector import RecipeDuplicateDetector
from app.services.recipe_import_service import RecipeImportService
from app.services.recipe_storage import RecipeStorage
from fastapi.testclient import TestClient
from PIL import Image


def _png() -> bytes:
    output = BytesIO()
    Image.new("RGB", (64, 32), "white").save(output, format="PNG")
    return output.getvalue()


def test_image_upload_uses_ai_and_returns_confirmable_preview(
    tmp_path,
    monkeypatch,
) -> None:
    repository = ImportSessionRepository()
    settings = Settings(
        _env_file=None,
        imports_path=tmp_path,
        ai_enabled=True,
        ai_enrich_missing_fields=False,
    )

    class FakeOrchestrator:
        async def parse_with_ai(self, import_id, *, reason):
            session = repository.get(import_id)
            session.previous_results.append(session.active_result)
            session.active_result = ImportResult(
                import_id=import_id,
                created_at=session.created_at,
                status=ImportStatus.SUCCESS,
                recipe=Recipe(
                    title="Recept uit afbeelding",
                    source_type=SourceType.IMAGE,
                    ingredients=[Ingredient(name="tomaat")],
                    instructions=["Snijd de tomaat."],
                ),
                extractor="ollama:qwen3.5:4b",
            )
            session.status = ImportProcessingStatus.AWAITING_CONFIRMATION
            session.metadata.parse_method = ParseMethod.AI_IMAGE
            session.metadata.ai_model = "qwen3.5:4b"
            return repository.update(session)

    monkeypatch.setattr("app.api.uploads.get_settings", lambda: settings)
    app.dependency_overrides[get_import_session_repository] = lambda: repository
    app.dependency_overrides[create_ai_import_orchestrator] = FakeOrchestrator
    recipes_path = tmp_path / "recipes"
    recipes_path.mkdir()
    import_service = RecipeImportService(
        importer=ManualTextRecipeImporter(),
        storage=RecipeStorage(
            recipes_path=recipes_path,
            renderer=RecipeMarkdownRenderer(),
        ),
        duplicate_detector=RecipeDuplicateDetector(recipes_path),
    )
    app.dependency_overrides[create_import_service] = lambda: import_service

    try:
        with TestClient(app) as client:
            response = client.post(
                "/imports/upload/preview",
                files={"file": ("recipe.png", _png(), "image/png")},
            )
            import_id = response.json()["import_id"]
            temporary_path = repository.get(UUID(import_id)).source.temporary_file_path
            confirm_response = client.post(f"/imports/{import_id}/confirm")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["recipe"]["title"] == "Recept uit afbeelding"
    assert body["metadata"]["parse_method"] == "ai_image"
    assert temporary_path is not None
    assert confirm_response.status_code == 200
    assert len(list(recipes_path.glob("*.md"))) == 1
    assert (
        repository.get(UUID(body["import_id"])).status is ImportProcessingStatus.SAVED
    )
    assert not temporary_path.exists()


def test_image_upload_rejects_corrupt_image(tmp_path, monkeypatch) -> None:
    settings = Settings(
        _env_file=None,
        imports_path=tmp_path,
        ai_enabled=True,
    )
    monkeypatch.setattr("app.api.uploads.get_settings", lambda: settings)

    with TestClient(app) as client:
        response = client.post(
            "/imports/upload/preview",
            files={"file": ("recipe.png", b"not-an-image", "image/png")},
        )

    assert response.status_code == 400
    assert "afbeelding" in response.json()["detail"].casefold()
