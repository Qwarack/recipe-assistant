from datetime import date

import pytest
from app.models.meal_plan_generation import MealPlanGenerationRequest
from pydantic import ValidationError


def test_generation_request_normalizes_weekdays_tags_and_identifiers() -> None:
    request = MealPlanGenerationRequest(
        start_date=date(2026, 7, 22),
        days_to_plan=[6, 2, 2],
        vegetarian_days=[3, 3],
        required_tags=[" Quick ", "ITALIAN"],
        excluded_recipe_identifiers=[" pasta ", "pasta", ""],
    )

    assert request.days_to_plan == [2, 6]
    assert request.vegetarian_days == [3]
    assert request.required_tags == ["italian", "quick"]
    assert request.excluded_recipe_identifiers == ["pasta"]


def test_generation_request_rejects_invalid_configuration() -> None:
    with pytest.raises(ValidationError):
        MealPlanGenerationRequest(days_to_plan=[7])
    with pytest.raises(ValidationError):
        MealPlanGenerationRequest(servings=0)
    with pytest.raises(ValidationError):
        MealPlanGenerationRequest(meal_type="snack")
