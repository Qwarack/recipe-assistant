from pathlib import Path

from app.database.base import Base
from app.database.engine import create_session_factory
from app.database.models.recipe import RecipeRecord
from app.database.repositories.recipe_repository import (
    RecipeRepository,
)


def test_add_and_get_recipe(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")

    engine = session_factory.kw["bind"]
    Base.metadata.create_all(engine)

    with session_factory() as session:
        repository = RecipeRepository(session)

        recipe = RecipeRecord(
            identifier="pasta-carbonara",
            title="Pasta Carbonara",
            file_path="data/recipes/pasta-carbonara.md",
            source_url="https://example.com/carbonara",
            content_hash="abc123",
        )

        repository.add(recipe)
        session.commit()

        result = repository.get_by_identifier("pasta-carbonara")

        assert result is not None
        assert result.id is not None
        assert result.title == "Pasta Carbonara"
        assert result.file_path == ("data/recipes/pasta-carbonara.md")


def test_get_recipe_returns_none_when_missing(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")

    engine = session_factory.kw["bind"]
    Base.metadata.create_all(engine)

    with session_factory() as session:
        repository = RecipeRepository(session)

        result = repository.get_by_identifier("bestaat-niet")

        assert result is None


def test_update_recipe(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")

    engine = session_factory.kw["bind"]
    Base.metadata.create_all(engine)

    with session_factory() as session:
        repository = RecipeRepository(session)

        recipe = RecipeRecord(
            identifier="pasta-carbonara",
            title="Pasta Carbonara",
            file_path="data/recipes/pasta-carbonara.md",
            source_url=None,
            content_hash=None,
        )

        repository.add(recipe)
        session.commit()

        repository.update(
            recipe,
            title="Romige Pasta Carbonara",
            file_path="data/recipes/romige-carbonara.md",
            source_url="https://example.com/carbonara",
            content_hash="updated-hash",
        )
        session.commit()

        result = repository.get_by_identifier("pasta-carbonara")

        assert result is not None
        assert result.title == "Romige Pasta Carbonara"
        assert result.file_path == ("data/recipes/romige-carbonara.md")
        assert result.source_url == ("https://example.com/carbonara")
        assert result.content_hash == "updated-hash"


def test_delete_recipe(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")

    engine = session_factory.kw["bind"]
    Base.metadata.create_all(engine)

    with session_factory() as session:
        repository = RecipeRepository(session)

        recipe = RecipeRecord(
            identifier="pasta-carbonara",
            title="Pasta Carbonara",
            file_path="data/recipes/pasta-carbonara.md",
            source_url=None,
            content_hash=None,
        )

        repository.add(recipe)
        session.commit()

        repository.delete(recipe)
        session.commit()

        result = repository.get_by_identifier("pasta-carbonara")

        assert result is None
