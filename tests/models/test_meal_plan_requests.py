from datetime import date

import pytest
from app.models.meal_plan_requests import (
    AddMealPlanEntryRequest,
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
