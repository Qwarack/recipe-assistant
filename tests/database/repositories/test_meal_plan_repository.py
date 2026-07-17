from datetime import date
from pathlib import Path

import pytest
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
from sqlalchemy.exc import IntegrityError


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


def test_get_for_date_returns_plan_containing_date(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")

    engine = session_factory.kw["bind"]
    Base.metadata.create_all(engine)

    with session_factory() as session:
        repository = MealPlanRepository(session)

        repository.add(
            MealPlanRecord(
                start_date=date(2026, 7, 15),
                name="Woensdagplanning",
            )
        )
        session.commit()

        result = repository.get_for_date(date(2026, 7, 19))

        assert result is not None
        assert result.start_date == date(2026, 7, 15)


def test_get_latest_returns_newest_plan(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")

    engine = session_factory.kw["bind"]
    Base.metadata.create_all(engine)

    with session_factory() as session:
        repository = MealPlanRepository(session)

        repository.add(
            MealPlanRecord(
                start_date=date(2026, 7, 8),
                name="Oude planning",
            )
        )
        repository.add(
            MealPlanRecord(
                start_date=date(2026, 7, 15),
                name="Nieuwe planning",
            )
        )
        session.commit()

        result = repository.get_latest()

        assert result is not None
        assert result.start_date == date(2026, 7, 15)


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


def test_get_and_delete_meal_plan_entry(
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

        session.add_all(
            [
                recipe,
                meal_plan,
            ]
        )
        session.flush()

        entry = MealPlanEntryRecord(
            meal_plan_id=meal_plan.id,
            recipe_id=recipe.id,
            planned_date=date(2026, 7, 17),
            meal_type="dinner",
            servings=2,
        )

        session.add(entry)
        session.commit()

        repository = MealPlanRepository(session)

        result = repository.get_entry_by_id(entry.id)

        assert result is not None
        assert result.recipe_id == recipe.id

        repository.delete_entry(result)
        session.commit()

        assert repository.get_entry_by_id(entry.id) is None


def test_get_entry_by_slot_can_exclude_current_entry(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")
    Base.metadata.create_all(session_factory.kw["bind"])

    with session_factory() as session:
        recipe = RecipeRecord(
            identifier="pasta-carbonara",
            title="Pasta Carbonara",
            file_path="data/recipes/pasta-carbonara.md",
        )
        plan = MealPlanRecord(start_date=date(2026, 7, 15))
        entry = MealPlanEntryRecord(
            meal_plan=plan,
            recipe=recipe,
            planned_date=date(2026, 7, 17),
            meal_type="dinner",
            servings=2,
        )
        session.add(entry)
        session.commit()
        repository = MealPlanRepository(session)

        found = repository.get_entry_by_slot(
            meal_plan_id=plan.id,
            planned_date=entry.planned_date,
            meal_type=entry.meal_type,
        )
        excluded = repository.get_entry_by_slot(
            meal_plan_id=plan.id,
            planned_date=entry.planned_date,
            meal_type=entry.meal_type,
            exclude_entry_id=entry.id,
        )

        assert found is entry
        assert excluded is None


def test_foreign_key_rejects_unknown_recipe(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")
    Base.metadata.create_all(session_factory.kw["bind"])

    with session_factory() as session:
        plan = MealPlanRecord(start_date=date(2026, 7, 15))
        session.add(plan)
        session.flush()
        session.add(
            MealPlanEntryRecord(
                meal_plan_id=plan.id,
                recipe_id=999,
                planned_date=date(2026, 7, 17),
                meal_type="dinner",
                servings=2,
            )
        )

        with pytest.raises(IntegrityError):
            session.commit()


def test_deleting_plan_cascades_to_entries(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")
    Base.metadata.create_all(session_factory.kw["bind"])

    with session_factory() as session:
        entry = MealPlanEntryRecord(
            meal_plan=MealPlanRecord(start_date=date(2026, 7, 15)),
            recipe=RecipeRecord(
                identifier="pasta-carbonara",
                title="Pasta Carbonara",
                file_path="data/recipes/pasta-carbonara.md",
            ),
            planned_date=date(2026, 7, 17),
            meal_type="dinner",
            servings=2,
        )
        session.add(entry)
        session.commit()
        entry_id = entry.id
        session.delete(entry.meal_plan)
        session.commit()

        assert session.get(MealPlanEntryRecord, entry_id) is None


def test_deleting_recipe_in_use_is_restricted(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")
    Base.metadata.create_all(session_factory.kw["bind"])

    with session_factory() as session:
        recipe = RecipeRecord(
            identifier="pasta-carbonara",
            title="Pasta Carbonara",
            file_path="data/recipes/pasta-carbonara.md",
        )
        session.add(
            MealPlanEntryRecord(
                meal_plan=MealPlanRecord(start_date=date(2026, 7, 15)),
                recipe=recipe,
                planned_date=date(2026, 7, 17),
                meal_type="dinner",
                servings=2,
            )
        )
        session.commit()
        recipe_id = recipe.id
        session.delete(recipe)

        with pytest.raises(IntegrityError):
            session.commit()

        session.rollback()
        assert session.get(RecipeRecord, recipe_id) is not None
