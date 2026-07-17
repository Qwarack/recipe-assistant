from datetime import date
from pathlib import Path

import pytest
from app.database.base import Base
from app.database.engine import create_session_factory
from app.database.models.meal_plan import MealPlanRecord
from app.database.models.meal_plan_entry import MealPlanEntryRecord
from app.database.models.recipe import RecipeRecord
from app.database.repositories.recipe_repository import (
    RecipeRepository,
)
from app.services.recipe_delete_service import (
    RecipeDeleteService,
    RecipeInUseError,
)


def test_delete_recipe_by_identifier(
    tmp_path: Path,
) -> None:
    recipe_path = tmp_path / "pasta-carbonara.md"

    recipe_path.write_text(
        "# Pasta Carbonara\n",
        encoding="utf-8",
    )

    service = RecipeDeleteService(recipes_path=tmp_path)

    deleted = service.delete_by_identifier("pasta-carbonara")

    assert deleted is True
    assert recipe_path.exists() is False


def test_delete_returns_false_when_recipe_is_missing(
    tmp_path: Path,
) -> None:
    service = RecipeDeleteService(recipes_path=tmp_path)

    deleted = service.delete_by_identifier("bestaat-niet")

    assert deleted is False


def test_delete_does_not_escape_recipes_directory(
    tmp_path: Path,
) -> None:
    outside_file = tmp_path.parent / "secret.md"

    outside_file.write_text(
        "# Secret\n",
        encoding="utf-8",
    )

    service = RecipeDeleteService(recipes_path=tmp_path)

    deleted = service.delete_by_identifier("../secret")

    assert deleted is False
    assert outside_file.exists() is True


def test_delete_removes_file_and_database_record(
    tmp_path: Path,
) -> None:
    recipe_path = tmp_path / "pasta-carbonara.md"
    recipe_path.write_text(
        "# Pasta Carbonara\n",
        encoding="utf-8",
    )

    session_factory = create_session_factory(tmp_path / "app.db")

    engine = session_factory.kw["bind"]
    Base.metadata.create_all(engine)

    with session_factory() as session:
        repository = RecipeRepository(session)

        repository.add(
            RecipeRecord(
                identifier="pasta-carbonara",
                title="Pasta Carbonara",
                file_path=str(recipe_path),
                source_url=None,
                content_hash=None,
            )
        )
        session.commit()

        service = RecipeDeleteService(
            recipes_path=tmp_path,
            session=session,
        )

        deleted = service.delete_by_identifier("pasta-carbonara")

        assert deleted is True
        assert recipe_path.exists() is False
        assert repository.get_by_identifier("pasta-carbonara") is None


def test_delete_keeps_planned_recipe_file_and_record(
    tmp_path: Path,
) -> None:
    recipe_path = tmp_path / "pasta-carbonara.md"
    recipe_path.write_text("# Pasta Carbonara\n", encoding="utf-8")
    session_factory = create_session_factory(tmp_path / "app.db")
    Base.metadata.create_all(session_factory.kw["bind"])

    with session_factory() as session:
        recipe = RecipeRecord(
            identifier="pasta-carbonara",
            title="Pasta Carbonara",
            file_path=str(recipe_path),
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
        service = RecipeDeleteService(recipes_path=tmp_path, session=session)

        with pytest.raises(RecipeInUseError):
            service.delete_by_identifier("pasta-carbonara")

        assert recipe_path.exists()
        stored_recipe = RecipeRepository(session).get_by_identifier("pasta-carbonara")
        assert stored_recipe is not None
