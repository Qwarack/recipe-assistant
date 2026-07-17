from collections.abc import Generator

from app.core.config import get_settings
from app.database.engine import create_session_factory
from app.services.recipe_index_sync_service import (
    RecipeIndexSyncService,
)


def create_recipe_index_sync_service() -> Generator[
    RecipeIndexSyncService,
    None,
    None,
]:
    settings = get_settings()
    session_factory = create_session_factory(settings.database_path)

    with session_factory() as session:
        yield RecipeIndexSyncService(
            session=session,
            recipes_path=settings.recipes_path,
        )
