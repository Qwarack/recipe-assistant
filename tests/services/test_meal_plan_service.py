from datetime import date
from pathlib import Path

import pytest
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
from app.services.meal_plan_errors import (
    InvalidServingsError,
    MealPlanDateOutsideRangeError,
    MealPlanEntryNotFoundError,
    MealPlanSlotOccupiedError,
    RecipeNotFoundError,
)
from app.services.meal_plan_service import (
    MealPlanService,
)


def test_add_recipe_to_custom_start_date_plan(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")

    engine = session_factory.kw["bind"]
    Base.metadata.create_all(engine)

    with session_factory() as session:
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

        entry = service.add_recipe(
            start_date=date(2026, 7, 15),
            planned_date=date(2026, 7, 17),
            recipe_identifier="pasta-carbonara",
            servings=3,
        )

        assert entry.id is not None
        assert entry.meal_plan.start_date == date(
            2026,
            7,
            15,
        )
        assert entry.planned_date == date(
            2026,
            7,
            17,
        )
        assert entry.servings == 3
        assert entry.recipe.title == "Pasta Carbonara"


def test_add_recipe_rejects_date_outside_plan(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")

    engine = session_factory.kw["bind"]
    Base.metadata.create_all(engine)

    with session_factory() as session:
        service = MealPlanService(session)

        with pytest.raises(
            MealPlanDateOutsideRangeError,
            match="seven-day meal plan period",
        ):
            service.add_recipe(
                start_date=date(2026, 7, 15),
                planned_date=date(2026, 7, 22),
                recipe_identifier="pasta-carbonara",
            )


def test_add_recipe_rejects_zero_servings(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")

    engine = session_factory.kw["bind"]
    Base.metadata.create_all(engine)

    with session_factory() as session:
        service = MealPlanService(session)

        with pytest.raises(
            InvalidServingsError,
            match="Servings must be at least 1",
        ):
            service.add_recipe(
                start_date=date(2026, 7, 15),
                planned_date=date(2026, 7, 15),
                recipe_identifier="pasta-carbonara",
                servings=0,
            )


def test_add_recipe_rejects_duplicate_meal_slot(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")

    engine = session_factory.kw["bind"]
    Base.metadata.create_all(engine)

    with session_factory() as session:
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
        recipe_repository.add(
            RecipeRecord(
                identifier="tomatensoep",
                title="Tomatensoep",
                file_path="data/recipes/tomatensoep.md",
                source_url=None,
                content_hash=None,
            )
        )
        session.commit()

        service = MealPlanService(session)

        service.add_recipe(
            start_date=date(2026, 7, 15),
            planned_date=date(2026, 7, 15),
            recipe_identifier="pasta-carbonara",
            meal_type="dinner",
        )

        with pytest.raises(
            MealPlanSlotOccupiedError,
            match="meal slot is already planned",
        ):
            service.add_recipe(
                start_date=date(2026, 7, 15),
                planned_date=date(2026, 7, 15),
                recipe_identifier="tomatensoep",
                meal_type="dinner",
            )


def test_get_plan_returns_plan_with_entries(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")

    engine = session_factory.kw["bind"]
    Base.metadata.create_all(engine)

    with session_factory() as session:
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
            meal_type="dinner",
            servings=2,
        )

        result = service.get_plan(date(2026, 7, 15))

        assert result is not None
        assert result.start_date == date(
            2026,
            7,
            15,
        )
        assert len(result.entries) == 1
        assert result.entries[0].recipe.title == ("Pasta Carbonara")


def test_get_plan_returns_none_when_missing(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")

    engine = session_factory.kw["bind"]
    Base.metadata.create_all(engine)

    with session_factory() as session:
        service = MealPlanService(session)

        result = service.get_plan(date(2026, 7, 15))

        assert result is None


def test_get_current_or_latest_plan_returns_current_plan(
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
                name="Huidige planning",
            )
        )
        session.commit()

        service = MealPlanService(session)

        result = service.get_current_or_latest_plan(date(2026, 7, 18))

        assert result is not None
        assert result.name == "Huidige planning"


def test_get_current_or_latest_plan_falls_back_to_latest(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")

    engine = session_factory.kw["bind"]
    Base.metadata.create_all(engine)

    with session_factory() as session:
        repository = MealPlanRepository(session)

        repository.add(
            MealPlanRecord(
                start_date=date(2026, 7, 1),
                name="Oude planning",
            )
        )
        repository.add(
            MealPlanRecord(
                start_date=date(2026, 7, 8),
                name="Nieuwste planning",
            )
        )
        session.commit()

        service = MealPlanService(session)

        result = service.get_current_or_latest_plan(date(2026, 7, 30))

        assert result is not None
        assert result.name == "Nieuwste planning"


def test_add_recipe_rejects_unknown_recipe(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")
    Base.metadata.create_all(session_factory.kw["bind"])

    with session_factory() as session:
        service = MealPlanService(session)

        with pytest.raises(RecipeNotFoundError):
            service.add_recipe(
                start_date=date(2026, 7, 15),
                planned_date=date(2026, 7, 17),
                recipe_identifier="onbekend",
            )


def test_remove_entry_returns_updated_plan(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")
    Base.metadata.create_all(session_factory.kw["bind"])

    with session_factory() as session:
        session.add(
            RecipeRecord(
                identifier="pasta-carbonara",
                title="Pasta Carbonara",
                file_path="data/recipes/pasta-carbonara.md",
            )
        )
        session.commit()
        service = MealPlanService(session)
        entry = service.add_recipe(
            start_date=date(2026, 7, 15),
            planned_date=date(2026, 7, 17),
            recipe_identifier="pasta-carbonara",
        )

        result = service.remove_entry(
            start_date=date(2026, 7, 15),
            entry_id=entry.id,
        )

        assert result.entries == []


def test_remove_entry_rejects_missing_or_wrong_plan(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")
    Base.metadata.create_all(session_factory.kw["bind"])

    with session_factory() as session:
        session.add(
            RecipeRecord(
                identifier="pasta-carbonara",
                title="Pasta Carbonara",
                file_path="data/recipes/pasta-carbonara.md",
            )
        )
        session.commit()
        service = MealPlanService(session)
        entry = service.add_recipe(
            start_date=date(2026, 7, 15),
            planned_date=date(2026, 7, 17),
            recipe_identifier="pasta-carbonara",
        )

        with pytest.raises(MealPlanEntryNotFoundError):
            service.remove_entry(
                start_date=date(2026, 7, 22),
                entry_id=entry.id,
            )
        with pytest.raises(MealPlanEntryNotFoundError):
            service.remove_entry(
                start_date=date(2026, 7, 15),
                entry_id=999,
            )


def test_update_entry_changes_fields_and_can_clear_notes(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")
    Base.metadata.create_all(session_factory.kw["bind"])

    with session_factory() as session:
        session.add(
            RecipeRecord(
                identifier="pasta-carbonara",
                title="Pasta Carbonara",
                file_path="data/recipes/pasta-carbonara.md",
            )
        )
        session.commit()
        service = MealPlanService(session)
        entry = service.add_recipe(
            start_date=date(2026, 7, 15),
            planned_date=date(2026, 7, 17),
            recipe_identifier="pasta-carbonara",
            notes="Extra kaas",
        )

        result = service.update_entry(
            start_date=date(2026, 7, 15),
            entry_id=entry.id,
            planned_date=date(2026, 7, 18),
            meal_type="lunch",
            servings=4,
            notes=None,
            update_notes=True,
        )

        updated = result.entries[0]
        assert updated.planned_date == date(2026, 7, 18)
        assert updated.meal_type == "lunch"
        assert updated.servings == 4
        assert updated.notes is None


def test_update_entry_rejects_occupied_slot(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")
    Base.metadata.create_all(session_factory.kw["bind"])

    with session_factory() as session:
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
        service = MealPlanService(session)
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

        with pytest.raises(MealPlanSlotOccupiedError):
            service.update_entry(
                start_date=date(2026, 7, 15),
                entry_id=first.id,
                planned_date=date(2026, 7, 18),
            )


def test_get_current_or_latest_plan_returns_none_when_empty(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")
    Base.metadata.create_all(session_factory.kw["bind"])

    with session_factory() as session:
        service = MealPlanService(session)

        assert service.get_current_or_latest_plan(date(2026, 7, 18)) is None
