from datetime import date
from pathlib import Path

from app.api import meal_plans as meal_plans_api
from app.database.base import Base
from app.database.engine import create_session_factory
from app.database.models.recipe import RecipeRecord
from app.main import app
from app.services.automatic_meal_planner import AutomaticMealPlanner
from fastapi.testclient import TestClient


def create_planner(tmp_path: Path, *, recipe_count: int = 8):
    session_factory = create_session_factory(tmp_path / "app.db")
    Base.metadata.create_all(session_factory.kw["bind"])
    session = session_factory()
    session.add_all(
        [
            RecipeRecord(
                identifier=f"recipe-{index}",
                title=f"Recipe {index}",
                file_path=f"recipe-{index}.md",
                tags=[],
                meal_types=["dinner"],
                preparation_time_minutes=30,
            )
            for index in range(recipe_count)
        ]
    )
    session.commit()
    planner = AutomaticMealPlanner(
        session=session,
        today_provider=lambda: date(2026, 7, 23),
    )
    return session, planner


def test_generation_api_full_draft_lifecycle(tmp_path: Path) -> None:
    session, planner = create_planner(tmp_path)
    app.dependency_overrides[meal_plans_api.create_automatic_meal_planner] = lambda: (
        planner
    )
    try:
        with TestClient(app) as client:
            generated = client.post(
                "/meal-plans/generate",
                json={
                    "start_date": "2026-07-22",
                    "servings": 3,
                    "avoid_recent_days": 0,
                    "random_seed": 123,
                },
            )
            body = generated.json()
            plan_id = body["plan"]["id"]
            entry_id = body["plan"]["entries"][0]["id"]
            rerolled = client.post(
                f"/meal-plans/{plan_id}/entries/{entry_id}/reroll",
                json={"random_seed": 124},
            )
            regenerated = client.post(
                f"/meal-plans/{plan_id}/regenerate",
                json={"random_seed": 125},
            )
            new_plan_id = regenerated.json()["plan"]["id"]
            cancelled = client.delete(f"/meal-plans/{new_plan_id}")
            activated = client.post(
                f"/meal-plans/{plan_id}/activate",
                json={"activated_by": "discord-user"},
            )
            cannot_delete_active = client.delete(f"/meal-plans/{plan_id}")
    finally:
        app.dependency_overrides.clear()
        session.close()

    assert generated.status_code == 201
    assert body["plan"]["status"] == "draft"
    assert body["generation_seed"] == 123
    assert len(body["plan"]["entries"]) == 7
    assert rerolled.status_code == 200
    assert rerolled.json()["generation_seed"] == 124
    assert regenerated.status_code == 201
    assert new_plan_id != plan_id
    assert cancelled.status_code == 204
    assert activated.status_code == 200
    assert activated.json()["status"] == "active"
    assert cannot_delete_active.status_code == 409


def test_generation_api_maps_validation_and_domain_errors(tmp_path: Path) -> None:
    session, planner = create_planner(tmp_path, recipe_count=0)
    app.dependency_overrides[meal_plans_api.create_automatic_meal_planner] = lambda: (
        planner
    )
    try:
        with TestClient(app) as client:
            invalid = client.post(
                "/meal-plans/generate",
                json={"days_to_plan": [7]},
            )
            generated = client.post(
                "/meal-plans/generate",
                json={"start_date": "2026-07-22", "random_seed": 1},
            )
            plan_id = generated.json()["plan"]["id"]
            incomplete = client.post(f"/meal-plans/{plan_id}/activate")
            missing = client.post("/meal-plans/999/regenerate")
            missing_reroll = client.post(f"/meal-plans/{plan_id}/entries/999/reroll")
    finally:
        app.dependency_overrides.clear()
        session.close()

    assert invalid.status_code == 422
    assert generated.status_code == 201
    assert len(generated.json()["unfilled_slots"]) == 7
    assert incomplete.status_code == 409
    assert missing.status_code == 404
    assert missing_reroll.status_code == 409
