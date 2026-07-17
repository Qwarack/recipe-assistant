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


def test_delete_recipe_by_identifier(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")

    engine = session_factory.kw["bind"]
    Base.metadata.create_all(engine)

    with session_factory() as session:
        repository = RecipeRepository(session)

        repository.add(
            RecipeRecord(
                identifier="pasta-carbonara",
                title="Pasta Carbonara",
                file_path="data/recipes/pasta-carbonara.md",
                source_url=None,
                content_hash=None,
            )
        )
        session.commit()

        deleted = repository.delete_by_identifier("pasta-carbonara")
        session.commit()

        assert deleted is True
        assert repository.get_by_identifier("pasta-carbonara") is None


def test_delete_by_identifier_returns_false_when_missing(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")

    engine = session_factory.kw["bind"]
    Base.metadata.create_all(engine)

    with session_factory() as session:
        repository = RecipeRepository(session)

        deleted = repository.delete_by_identifier("bestaat-niet")

        assert deleted is False


def test_search_recipes_by_title(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")

    engine = session_factory.kw["bind"]
    Base.metadata.create_all(engine)

    with session_factory() as session:
        repository = RecipeRepository(session)

        repository.add(
            RecipeRecord(
                identifier="pasta-carbonara",
                title="Pasta Carbonara",
                file_path="data/recipes/pasta-carbonara.md",
                source_url=None,
                content_hash=None,
            )
        )
        repository.add(
            RecipeRecord(
                identifier="pasta-pesto",
                title="Pasta Pesto",
                file_path="data/recipes/pasta-pesto.md",
                source_url=None,
                content_hash=None,
            )
        )
        repository.add(
            RecipeRecord(
                identifier="tomatensoep",
                title="Tomatensoep",
                file_path="data/recipes/tomatensoep.md",
                source_url=None,
                content_hash=None,
            )
        )

        session.commit()

        results = repository.search_by_title("pasta")

        assert [recipe.title for recipe in results] == [
            "Pasta Carbonara",
            "Pasta Pesto",
        ]


def test_search_recipes_respects_limit(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")

    engine = session_factory.kw["bind"]
    Base.metadata.create_all(engine)

    with session_factory() as session:
        repository = RecipeRepository(session)

        for index in range(5):
            repository.add(
                RecipeRecord(
                    identifier=f"pasta-{index}",
                    title=f"Pasta {index}",
                    file_path=f"data/recipes/pasta-{index}.md",
                    source_url=None,
                    content_hash=None,
                )
            )

        session.commit()

        results = repository.search_by_title(
            "pasta",
            limit=2,
        )

        assert len(results) == 2
