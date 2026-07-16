from pathlib import Path

from app.api import search as search_api
from app.main import app
from app.services.recipe_delete_service import (
    RecipeDeleteService,
)
from fastapi.testclient import TestClient


def test_delete_recipe_endpoint(
    tmp_path: Path,
) -> None:
    recipe_path = tmp_path / "pasta-carbonara.md"

    recipe_path.write_text(
        "# Pasta Carbonara\n",
        encoding="utf-8",
    )

    app.dependency_overrides[search_api.create_recipe_delete_service] = lambda: (
        RecipeDeleteService(recipes_path=tmp_path)
    )

    try:
        with TestClient(app) as client:
            response = client.delete("/recipes/pasta-carbonara")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 204
    assert response.content == b""
    assert recipe_path.exists() is False


def test_delete_recipe_endpoint_returns_404_when_missing(
    tmp_path: Path,
) -> None:
    app.dependency_overrides[search_api.create_recipe_delete_service] = lambda: (
        RecipeDeleteService(recipes_path=tmp_path)
    )

    try:
        with TestClient(app) as client:
            response = client.delete("/recipes/bestaat-niet")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json() == {"detail": "Recipe not found"}
