from pathlib import Path

from app.database.base import Base
from app.database.engine import create_session_factory
from app.database.repositories.recipe_repository import RecipeRepository
from app.services.recipe_index_watcher import RecipeIndexWatcher


def _write_recipe(path: Path, *, title: str, meal_type: str) -> None:
    path.write_text(
        f"""---
title: {title}
meal_types: [{meal_type}]
---
""",
        encoding="utf-8",
    )


def test_watcher_syncs_new_and_changed_obsidian_recipe(tmp_path: Path) -> None:
    recipes_path = tmp_path / "recepten"
    recipes_path.mkdir()
    database_path = tmp_path / "app.db"
    session_factory = create_session_factory(database_path)
    Base.metadata.create_all(session_factory.kw["bind"])
    watcher = RecipeIndexWatcher(
        session_factory=session_factory,
        recipes_path=recipes_path,
    )
    recipe_path = recipes_path / "drankje.md"
    _write_recipe(recipe_path, title="Drankje", meal_type="drank")

    assert watcher.sync_if_stable_change() is False
    assert watcher.sync_if_stable_change() is True

    with session_factory() as session:
        recipe = RecipeRepository(session).get_by_identifier("drankje")
        assert recipe is not None
        assert recipe.title == "Drankje"
        assert recipe.meal_types == ["drink"]

    _write_recipe(recipe_path, title="Nieuw drankje", meal_type="drank")

    assert watcher.sync_if_stable_change() is False
    assert watcher.sync_if_stable_change() is True

    with session_factory() as session:
        recipe = RecipeRepository(session).get_by_identifier("drankje")
        assert recipe is not None
        assert recipe.title == "Nieuw drankje"


def test_watcher_does_not_resync_unchanged_snapshot(tmp_path: Path) -> None:
    recipes_path = tmp_path / "recepten"
    recipes_path.mkdir()
    session_factory = create_session_factory(tmp_path / "app.db")
    Base.metadata.create_all(session_factory.kw["bind"])
    watcher = RecipeIndexWatcher(
        session_factory=session_factory,
        recipes_path=recipes_path,
    )

    assert watcher.sync_if_stable_change() is False
    assert watcher.sync_if_stable_change() is True
    assert watcher.sync_if_stable_change() is False
