from datetime import date
from pathlib import Path

from app.database.base import Base
from app.database.engine import create_session_factory
from app.database.models.meal_plan import MealPlanRecord
from app.database.models.meal_plan_entry import (
    MealPlanEntryRecord,
)
from app.database.models.recipe import RecipeRecord
from app.database.repositories.meal_plan_repository import (
    MealPlanRepository,
)


def test_add_and_get_meal_plan_by_start_date(
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

        meal_plan.entries.append(
            MealPlanEntryRecord(
                recipe=recipe,
                planned_date=date(2026, 7, 15),
                meal_type="dinner",
                servings=2,
            )
        )

        repository = MealPlanRepository(session)
        repository.add(meal_plan)
        session.commit()

        result = repository.get_by_start_date(date(2026, 7, 15))

        assert result is not None
        assert result.name == "Boodschappenweek"
        assert len(result.entries) == 1
        assert result.entries[0].recipe.title == ("Pasta Carbonara")


def test_get_meal_plan_returns_none_when_missing(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")

    engine = session_factory.kw["bind"]
    Base.metadata.create_all(engine)

    with session_factory() as session:
        repository = MealPlanRepository(session)

        result = repository.get_by_start_date(date(2026, 7, 15))

        assert result is None


def test_get_or_create_creates_new_meal_plan(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")

    engine = session_factory.kw["bind"]
    Base.metadata.create_all(engine)

    with session_factory() as session:
        repository = MealPlanRepository(session)

        result = repository.get_or_create(
            start_date=date(2026, 7, 15),
            name="Boodschappenweek",
        )

        session.commit()

        assert result.id is not None
        assert result.start_date == date(2026, 7, 15)
        assert result.name == "Boodschappenweek"


def test_get_or_create_returns_existing_meal_plan(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")

    engine = session_factory.kw["bind"]
    Base.metadata.create_all(engine)

    with session_factory() as session:
        repository = MealPlanRepository(session)

        first = repository.get_or_create(
            start_date=date(2026, 7, 15),
            name="Eerste naam",
        )
        session.commit()

        second = repository.get_or_create(
            start_date=date(2026, 7, 15),
            name="Andere naam",
        )

        assert second.id == first.id
        assert second.name == "Eerste naam"
