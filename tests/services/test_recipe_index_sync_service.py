from pathlib import Path

import pytest
from app.database.base import Base
from app.database.engine import create_session_factory
from app.database.repositories.recipe_repository import (
    RecipeRepository,
)
from app.services.recipe_index_sync_service import (
    RecipeIndexSyncService,
)


def test_sync_adds_markdown_recipe_to_database(
    tmp_path: Path,
) -> None:
    recipes_path = tmp_path / "recipes"
    recipes_path.mkdir()

    recipe_path = recipes_path / "pasta-carbonara.md"
    recipe_path.write_text(
        """---
title: Pasta Carbonara
source_url: https://example.com/carbonara
content_hash: abc123
---

# Pasta Carbonara
""",
        encoding="utf-8",
    )

    session_factory = create_session_factory(tmp_path / "app.db")
    engine = session_factory.kw["bind"]
    Base.metadata.create_all(engine)

    with session_factory() as session:
        service = RecipeIndexSyncService(
            session=session,
            recipes_path=recipes_path,
        )

        synced_count = service.sync_all()

        repository = RecipeRepository(session)
        result = repository.get_by_identifier("pasta-carbonara")

        assert synced_count == 1
        assert result is not None
        assert result.title == "Pasta Carbonara"
        assert result.file_path == str(recipe_path)
        assert result.source_url == ("https://example.com/carbonara")
        assert result.content_hash == "abc123"


def test_sync_updates_existing_record(
    tmp_path: Path,
) -> None:
    recipes_path = tmp_path / "recipes"
    recipes_path.mkdir()

    recipe_path = recipes_path / "pasta-carbonara.md"
    recipe_path.write_text(
        """---
title: Pasta Carbonara
---

# Pasta Carbonara
""",
        encoding="utf-8",
    )

    session_factory = create_session_factory(tmp_path / "app.db")
    engine = session_factory.kw["bind"]
    Base.metadata.create_all(engine)

    with session_factory() as session:
        service = RecipeIndexSyncService(
            session=session,
            recipes_path=recipes_path,
        )

        service.sync_all()

        recipe_path.write_text(
            """---
title: Romige Pasta Carbonara
---

# Romige Pasta Carbonara
""",
            encoding="utf-8",
        )

        service.sync_all()

        repository = RecipeRepository(session)
        result = repository.get_by_identifier("pasta-carbonara")

        assert result is not None
        assert result.title == ("Romige Pasta Carbonara")


def test_sync_file_adds_single_recipe(
    tmp_path: Path,
) -> None:
    recipes_path = tmp_path / "recipes"
    recipes_path.mkdir()

    first_recipe = recipes_path / "pasta.md"
    first_recipe.write_text(
        """---
title: Pasta
---

# Pasta
""",
        encoding="utf-8",
    )

    second_recipe = recipes_path / "soep.md"
    second_recipe.write_text(
        """---
title: Soep
---

# Soep
""",
        encoding="utf-8",
    )

    session_factory = create_session_factory(tmp_path / "app.db")
    engine = session_factory.kw["bind"]
    Base.metadata.create_all(engine)

    with session_factory() as session:
        service = RecipeIndexSyncService(
            session=session,
            recipes_path=recipes_path,
        )

        service.sync_file(first_recipe)

        repository = RecipeRepository(session)

        assert repository.get_by_identifier("pasta") is not None

        assert repository.get_by_identifier("soep") is None


def test_sync_file_rejects_missing_file(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")
    engine = session_factory.kw["bind"]
    Base.metadata.create_all(engine)

    with session_factory() as session:
        service = RecipeIndexSyncService(
            session=session,
            recipes_path=tmp_path / "recipes",
        )

        with pytest.raises(
            FileNotFoundError,
            match="Recipe file does not exist",
        ):
            service.sync_file(tmp_path / "recipes" / "missing.md")


def test_remove_by_identifier_removes_recipe(
    tmp_path: Path,
) -> None:
    recipes_path = tmp_path / "recipes"
    recipes_path.mkdir()
    recipe_path = recipes_path / "pasta.md"
    recipe_path.write_text(
        "---\ntitle: Pasta\n---\n",
        encoding="utf-8",
    )

    session_factory = create_session_factory(tmp_path / "app.db")
    engine = session_factory.kw["bind"]
    Base.metadata.create_all(engine)

    with session_factory() as session:
        service = RecipeIndexSyncService(
            session=session,
            recipes_path=recipes_path,
        )
        service.sync_file(recipe_path)

        removed = service.remove_by_identifier("pasta")

        repository = RecipeRepository(session)

        assert removed is True
        assert repository.get_by_identifier("pasta") is None


def test_remove_by_identifier_returns_false_when_missing(
    tmp_path: Path,
) -> None:
    session_factory = create_session_factory(tmp_path / "app.db")
    engine = session_factory.kw["bind"]
    Base.metadata.create_all(engine)

    with session_factory() as session:
        service = RecipeIndexSyncService(
            session=session,
            recipes_path=tmp_path / "recipes",
        )

        removed = service.remove_by_identifier("bestaat-niet")

        assert removed is False
