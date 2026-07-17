from datetime import date
from pathlib import Path

from app.api import meal_plans as meal_plans_api
from app.database.base import Base
from app.database.engine import create_session_factory
from app.database.models.meal_plan import MealPlanRecord
from app.database.models.recipe import RecipeRecord
from app.database.repositories.meal_plan_repository import (
    MealPlanRepository,
)
from app.database.repositories.recipe_repository import (
    RecipeRepository,
)
from app.main import app
from app.services.meal_plan_service import (
    MealPlanService,
)
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session


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


def test_get_current_meal_plan_endpoint(
    tmp_path: Path,
    monkeypatch,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")

    engine = session_factory.kw["bind"]
    Base.metadata.create_all(engine)

    session = session_factory()

    repository = MealPlanRepository(session)
    repository.add(
        MealPlanRecord(
            start_date=date(2026, 7, 15),
            name="Huidige planning",
        )
    )
    session.commit()

    service = MealPlanService(session)

    app.dependency_overrides[meal_plans_api.create_meal_plan_service] = lambda: service

    monkeypatch.setattr(
        meal_plans_api,
        "get_local_today",
        lambda: date(2026, 7, 18),
    )

    try:
        with TestClient(app) as client:
            response = client.get("/meal-plans/current")
    finally:
        app.dependency_overrides.clear()
        session.close()

    assert response.status_code == 200

    body = response.json()

    assert body["name"] == "Huidige planning"
    assert body["start_date"] == "2026-07-15"


def test_get_current_meal_plan_returns_404_when_empty(
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
            response = client.get("/meal-plans/current")
    finally:
        app.dependency_overrides.clear()
        session.close()

    assert response.status_code == 404
    assert response.json() == {"detail": "No meal plans found"}


def test_add_meal_plan_entry_endpoint(
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

    app.dependency_overrides[meal_plans_api.create_meal_plan_service] = lambda: service

    try:
        with TestClient(app) as client:
            response = client.post(
                "/meal-plans/2026-07-15/entries",
                json={
                    "planned_date": "2026-07-17",
                    "recipe_identifier": "pasta-carbonara",
                    "meal_type": "dinner",
                    "servings": 3,
                    "notes": "Extra kaas",
                    "plan_name": "Boodschappenweek",
                },
            )
    finally:
        app.dependency_overrides.clear()
        session.close()

    assert response.status_code == 201

    body = response.json()

    assert body["start_date"] == "2026-07-15"
    assert body["end_date"] == "2026-07-21"
    assert body["name"] == "Boodschappenweek"
    assert len(body["entries"]) == 1
    assert body["entries"][0]["recipe_title"] == ("Pasta Carbonara")
    assert body["entries"][0]["servings"] == 3


def test_add_meal_plan_entry_endpoint_rejects_duplicate_slot(
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

    app.dependency_overrides[meal_plans_api.create_meal_plan_service] = lambda: service

    payload = {
        "planned_date": "2026-07-17",
        "recipe_identifier": "pasta-carbonara",
        "meal_type": "dinner",
        "servings": 2,
    }

    try:
        with TestClient(app) as client:
            first_response = client.post(
                "/meal-plans/2026-07-15/entries",
                json=payload,
            )
            second_response = client.post(
                "/meal-plans/2026-07-15/entries",
                json=payload,
            )
    finally:
        app.dependency_overrides.clear()
        session.close()

    assert first_response.status_code == 201
    assert second_response.status_code == 409
    assert second_response.json() == {"detail": "This meal slot is already planned"}


def _create_service_with_recipes(tmp_path: Path) -> tuple[Session, MealPlanService]:
    session_factory = create_session_factory(tmp_path / "app.db")
    Base.metadata.create_all(session_factory.kw["bind"])
    session = session_factory()
    session.add_all(
        [
            RecipeRecord(
                identifier="pasta-carbonara",
                title="Pasta Carbonara",
                file_path="data/recipes/pasta-carbonara.md",
            ),
            RecipeRecord(
                identifier="tomatensoep",
                title="Tomatensoep",
                file_path="data/recipes/tomatensoep.md",
            ),
        ]
    )
    session.commit()
    return session, MealPlanService(session)


def test_update_and_delete_meal_plan_entry_endpoints(
    tmp_path: Path,
) -> None:
    session, service = _create_service_with_recipes(tmp_path)
    entry = service.add_recipe(
        start_date=date(2026, 7, 15),
        planned_date=date(2026, 7, 17),
        recipe_identifier="pasta-carbonara",
        notes="Extra kaas",
    )
    app.dependency_overrides[meal_plans_api.create_meal_plan_service] = lambda: service

    try:
        with TestClient(app) as client:
            update_response = client.patch(
                f"/meal-plans/2026-07-15/entries/{entry.id}",
                json={
                    "planned_date": "2026-07-18",
                    "meal_type": "lunch",
                    "servings": 4,
                    "notes": None,
                },
            )
            delete_response = client.delete(
                f"/meal-plans/2026-07-15/entries/{entry.id}"
            )
    finally:
        app.dependency_overrides.clear()
        session.close()

    assert update_response.status_code == 200
    updated_entry = update_response.json()["entries"][0]
    assert updated_entry["planned_date"] == "2026-07-18"
    assert updated_entry["meal_type"] == "lunch"
    assert updated_entry["servings"] == 4
    assert updated_entry["notes"] is None
    assert delete_response.status_code == 200
    assert delete_response.json()["entries"] == []


def test_meal_plan_endpoints_map_domain_errors(
    tmp_path: Path,
) -> None:
    session, service = _create_service_with_recipes(tmp_path)
    first = service.add_recipe(
        start_date=date(2026, 7, 15),
        planned_date=date(2026, 7, 17),
        recipe_identifier="pasta-carbonara",
    )
    service.add_recipe(
        start_date=date(2026, 7, 15),
        planned_date=date(2026, 7, 18),
        recipe_identifier="tomatensoep",
    )
    app.dependency_overrides[meal_plans_api.create_meal_plan_service] = lambda: service

    try:
        with TestClient(app) as client:
            not_found = client.delete("/meal-plans/2026-07-15/entries/999")
            occupied = client.patch(
                f"/meal-plans/2026-07-15/entries/{first.id}",
                json={"planned_date": "2026-07-18"},
            )
            empty_update = client.patch(
                f"/meal-plans/2026-07-15/entries/{first.id}",
                json={},
            )
            outside_range = client.post(
                "/meal-plans/2026-07-15/entries",
                json={
                    "planned_date": "2026-07-22",
                    "recipe_identifier": "pasta-carbonara",
                },
            )
            unknown_recipe = client.post(
                "/meal-plans/2026-07-15/entries",
                json={
                    "planned_date": "2026-07-19",
                    "recipe_identifier": "onbekend",
                },
            )
    finally:
        app.dependency_overrides.clear()
        session.close()

    assert not_found.status_code == 404
    assert occupied.status_code == 409
    assert empty_update.status_code == 422
    assert outside_range.status_code == 422
    assert unknown_recipe.status_code == 404
