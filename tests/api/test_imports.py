from pathlib import Path

from app.api import imports as imports_api
from app.main import app
from app.models.import_result import ImportResult, ImportStatus
from app.models.recipe import Ingredient, Recipe, SourceType
from fastapi.testclient import TestClient


class FakeImportService:
    def __init__(
        self,
        result: ImportResult,
        destination: Path | None,
    ) -> None:
        self.result = result
        self.destination = destination

    def import_and_save(
        self,
        source: str,
    ) -> tuple[ImportResult, Path | None]:
        return self.result, self.destination


def test_website_import_endpoint_returns_created_file(
    tmp_path: Path,
) -> None:
    result = ImportResult(
        status=ImportStatus.SUCCESS,
        recipe=Recipe(
            title="Pasta",
            source_type=SourceType.WEBSITE,
            source_url="https://example.com/pasta",
            ingredients=[
                Ingredient(name="pasta"),
            ],
            instructions=[
                "Cook the pasta.",
            ],
        ),
    )

    destination = tmp_path / "pasta.md"

    app.dependency_overrides[imports_api.create_import_service] = lambda: (
        FakeImportService(result, destination)
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                "/imports/website",
                json={
                    "url": "https://example.com/pasta",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 201

    body = response.json()

    assert body["status"] == "success"
    assert body["destination"] == str(destination)
    assert body["warnings"] == []


def test_website_import_endpoint_returns_422_for_failed_import() -> None:
    result = ImportResult(
        status=ImportStatus.FAILED,
    )

    app.dependency_overrides[imports_api.create_import_service] = lambda: (
        FakeImportService(result, None)
    )

    try:
        with TestClient(app) as client:
            response = client.post(
                "/imports/website",
                json={
                    "url": "https://example.com/not-a-recipe",
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422
    assert response.json()["detail"]["import_id"] == str(result.import_id)
