from datetime import date
from pathlib import Path

from app.api import meal_plans as meal_plans_api
from app.database.base import Base
from app.database.engine import create_session_factory
from app.database.models.recipe import RecipeRecord
from app.database.repositories.recipe_repository import (
    RecipeRepository,
)
from app.main import app
from app.services.meal_plan_service import (
    MealPlanService,
)
from fastapi.testclient import TestClient


def test_get_meal_plan_endpoint(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")

    engine = session_factory.kw["bind"]
    Base.metadata.create_all(engine)

    session = session_factory()

    recipe_repository = RecipeRepository(session)
    recipe_repository.add(
        RecipeRecord(
            identifier="pasta-carbonara",
            title="Pasta Carbonara",
            file_path="data/recipes/pasta-carbonara.md",
            source_url=None,
            content_hash=None,
        )
    )
    session.commit()

    service = MealPlanService(session)

    service.add_recipe(
        start_date=date(2026, 7, 15),
        planned_date=date(2026, 7, 16),
        recipe_identifier="pasta-carbonara",
        servings=2,
    )

    app.dependency_overrides[meal_plans_api.create_meal_plan_service] = lambda: service

    try:
        with TestClient(app) as client:
            response = client.get("/meal-plans/2026-07-15")
    finally:
        app.dependency_overrides.clear()
        session.close()

    assert response.status_code == 200

    body = response.json()

    assert body["start_date"] == "2026-07-15"
    assert body["end_date"] == "2026-07-21"
    assert len(body["entries"]) == 1
    assert body["entries"][0]["recipe_title"] == ("Pasta Carbonara")


def test_get_meal_plan_endpoint_returns_404(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")

    engine = session_factory.kw["bind"]
    Base.metadata.create_all(engine)

    session = session_factory()
    service = MealPlanService(session)

    app.dependency_overrides[meal_plans_api.create_meal_plan_service] = lambda: service

    try:
        with TestClient(app) as client:
            response = client.get("/meal-plans/2026-07-15")
    finally:
        app.dependency_overrides.clear()
        session.close()

    assert response.status_code == 404
    assert response.json() == {"detail": "Meal plan not found"}
