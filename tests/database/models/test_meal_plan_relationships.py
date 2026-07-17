from datetime import date
from pathlib import Path

from app.database.base import Base
from app.database.engine import create_session_factory
from app.database.models.meal_plan import MealPlanRecord
from app.database.models.meal_plan_entry import (
    MealPlanEntryRecord,
)
from app.database.models.recipe import RecipeRecord


def test_meal_plan_relationships(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")

    engine = session_factory.kw["bind"]
    Base.metadata.create_all(engine)

    with session_factory() as session:
        recipe = RecipeRecord(
            identifier="pasta-carbonara",
            title="Pasta Carbonara",
            file_path="data/recipes/pasta-carbonara.md",
            source_url=None,
            content_hash=None,
        )

        meal_plan = MealPlanRecord(
            start_date=date(2026, 7, 15),
            name="Boodschappenweek",
        )

        entry = MealPlanEntryRecord(
            meal_plan=meal_plan,
            recipe=recipe,
            planned_date=date(2026, 7, 15),
            meal_type="dinner",
            servings=2,
        )

        session.add(entry)
        session.commit()

        assert meal_plan.entries == [entry]
        assert entry.meal_plan is meal_plan
        assert entry.recipe is recipe
        assert recipe.meal_plan_entries == [entry]
