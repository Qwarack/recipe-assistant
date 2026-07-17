from pathlib import Path

from app.api import search as search_api
from app.database.base import Base
from app.database.engine import create_session_factory
from app.database.models.recipe import RecipeRecord
from app.database.repositories.recipe_repository import (
    RecipeRepository,
)
from app.main import app
from app.services.database_recipe_search_service import (
    DatabaseRecipeSearchService,
)
from fastapi.testclient import TestClient


def test_search_recipes_endpoint(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")

    engine = session_factory.kw["bind"]
    Base.metadata.create_all(engine)

    session = session_factory()
    repository = RecipeRepository(session)

    repository.add(
        RecipeRecord(
            identifier="pasta-carbonara",
            title="Pasta Carbonara",
            file_path="data/recipes/pasta-carbonara.md",
            source_url="https://example.com/carbonara",
            content_hash=None,
        )
    )
    session.commit()

    service = DatabaseRecipeSearchService(repository=repository)

    app.dependency_overrides[search_api.create_recipe_search_service] = lambda: service

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
        session.close()

    assert response.status_code == 200

    body = response.json()

    assert len(body) == 1
    assert body[0]["identifier"] == "pasta-carbonara"
    assert body[0]["title"] == "Pasta Carbonara"
    assert body[0]["path"] == "data/recipes/pasta-carbonara.md"
    assert body[0]["source_url"] == ("https://example.com/carbonara")
