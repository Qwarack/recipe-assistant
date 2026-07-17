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
            ValueError,
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
            ValueError,
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
            ValueError,
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
