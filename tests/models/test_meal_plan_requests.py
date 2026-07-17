from datetime import date

import pytest
from app.models.meal_plan_requests import (
    AddMealPlanEntryRequest,
    UpdateMealPlanEntryRequest,
)
from pydantic import ValidationError


def test_add_meal_plan_entry_request() -> None:
    request = AddMealPlanEntryRequest(
        planned_date=date(2026, 7, 17),
        recipe_identifier="pasta-carbonara",
        servings=3,
    )

    assert request.planned_date == date(2026, 7, 17)
    assert request.meal_type == "dinner"
    assert request.servings == 3


def test_add_meal_plan_entry_rejects_zero_servings() -> None:
    with pytest.raises(ValidationError):
        AddMealPlanEntryRequest(
            planned_date=date(2026, 7, 17),
            recipe_identifier="pasta-carbonara",
            servings=0,
        )


def test_update_request_distinguishes_missing_and_cleared_notes() -> None:
    missing = UpdateMealPlanEntryRequest()
    cleared = UpdateMealPlanEntryRequest(notes=None)

    assert "notes" not in missing.model_fields_set
    assert "notes" in cleared.model_fields_set


def test_meal_plan_requests_reject_unknown_meal_type() -> None:
    with pytest.raises(ValidationError):
        UpdateMealPlanEntryRequest(meal_type="snack")
