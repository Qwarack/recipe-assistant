from pathlib import Path

from app.api import search as search_api
from app.main import app
from app.services.recipe_search_service import (
    RecipeSearchService,
)
from fastapi.testclient import TestClient


def test_search_recipes_endpoint(
    tmp_path: Path,
) -> None:
    recipe_path = tmp_path / "pasta-carbonara.md"

    recipe_path.write_text(
        """---
title: Pasta Carbonara
tags:
  - pasta
meal_types:
  - dinner
source_url: https://example.com/carbonara
---

# Pasta Carbonara
""",
        encoding="utf-8",
    )

    app.dependency_overrides[search_api.create_recipe_search_service] = lambda: (
        RecipeSearchService(recipes_path=tmp_path)
    )

    try:
        with TestClient(app) as client:
            response = client.get(
                "/recipes/search",
                params={
                    "query": "carbonara",
                    "limit": 10,
                },
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    body = response.json()

    assert len(body) == 1
    assert body[0]["title"] == "Pasta Carbonara"
    assert body[0]["path"] == str(recipe_path)
    assert body[0]["source_url"] == ("https://example.com/carbonara")
