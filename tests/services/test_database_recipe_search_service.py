from pathlib import Path

from app.database.base import Base
from app.database.engine import create_session_factory
from app.database.models.recipe import RecipeRecord
from app.database.repositories.recipe_repository import (
    RecipeRepository,
)
from app.services.database_recipe_search_service import (
    DatabaseRecipeSearchService,
)


def test_search_returns_database_recipes(
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
                source_url="https://example.com/carbonara",
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

        service = DatabaseRecipeSearchService(repository=repository)

        results = service.search("pasta")

        assert len(results) == 1
        assert results[0].identifier == "pasta-carbonara"
        assert results[0].title == "Pasta Carbonara"
        assert results[0].path == ("data/recipes/pasta-carbonara.md")
        assert str(results[0].source_url) == ("https://example.com/carbonara")


def test_search_returns_empty_list_for_blank_query(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")

    engine = session_factory.kw["bind"]
    Base.metadata.create_all(engine)

    with session_factory() as session:
        repository = RecipeRepository(session)
        service = DatabaseRecipeSearchService(repository=repository)

        results = service.search("   ")

        assert results == []
