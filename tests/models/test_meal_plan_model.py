from datetime import date

from app.models.meal_plan import (
    MealPlanDetail,
    MealPlanEntryDetail,
)


def test_meal_plan_detail_model() -> None:
    entry = MealPlanEntryDetail(
        id=1,
        planned_date=date(2026, 7, 16),
        meal_type="dinner",
        servings=2,
        notes=None,
        recipe_identifier="pasta-carbonara",
        recipe_title="Pasta Carbonara",
    )

    plan = MealPlanDetail(
        id=10,
        start_date=date(2026, 7, 15),
        end_date=date(2026, 7, 21),
        name="Boodschappenweek",
        entries=[entry],
    )

    assert plan.start_date == date(2026, 7, 15)
    assert plan.end_date == date(2026, 7, 21)
    assert plan.entries[0].recipe_title == ("Pasta Carbonara")
