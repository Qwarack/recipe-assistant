from pathlib import Path

from app.database.base import Base
from app.database.engine import create_session_factory
from app.database.models.recipe import RecipeRecord
from app.database.repositories.recipe_repository import (
    RecipeRepository,
)
from app.services.recipe_delete_service import (
    RecipeDeleteService,
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
