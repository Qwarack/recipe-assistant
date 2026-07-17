from datetime import date

from app.database.models.meal_plan import (
    MealPlanRecord,
)
from app.database.models.meal_plan_entry import (
    MealPlanEntryRecord,
)
from app.database.models.recipe import RecipeRecord
from app.services.meal_plan_mapper import (
    map_meal_plan_detail,
)


def test_maps_meal_plan_record_to_detail() -> None:
    recipe = RecipeRecord(
        id=5,
        identifier="pasta-carbonara",
        title="Pasta Carbonara",
        file_path="data/recipes/pasta-carbonara.md",
        source_url=None,
        content_hash=None,
    )

    entry = MealPlanEntryRecord(
        id=8,
        recipe=recipe,
        planned_date=date(2026, 7, 16),
        meal_type="dinner",
        servings=3,
        notes="Extra kaas",
    )

    meal_plan = MealPlanRecord(
        id=10,
        start_date=date(2026, 7, 15),
        name="Boodschappenweek",
        entries=[entry],
    )

    result = map_meal_plan_detail(meal_plan)

    assert result.id == 10
    assert result.start_date == date(2026, 7, 15)
    assert result.end_date == date(2026, 7, 21)
    assert result.name == "Boodschappenweek"

    assert len(result.entries) == 1
    assert result.entries[0].id == 8
    assert result.entries[0].recipe_identifier == ("pasta-carbonara")
    assert result.entries[0].recipe_title == ("Pasta Carbonara")
    assert result.entries[0].servings == 3
    assert result.entries[0].notes == "Extra kaas"
