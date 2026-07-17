from pathlib import Path

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
