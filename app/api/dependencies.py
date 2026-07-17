from collections.abc import Generator
from functools import lru_cache
from pathlib import Path
from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.database.engine import create_session_factory
from app.services.recipe_index_sync_service import (
    RecipeIndexSyncService,
)


@lru_cache
def get_session_factory(database_path: Path) -> sessionmaker[Session]:
    return create_session_factory(database_path)


def get_database_session() -> Generator[Session, None, None]:
    settings = get_settings()
    session_factory = get_session_factory(settings.database_path)

    with session_factory() as session:
        try:
            yield session
        except Exception:
            session.rollback()
            raise


def create_recipe_index_sync_service(
    session: Annotated[Session, Depends(get_database_session)],
) -> Generator[
    RecipeIndexSyncService,
    None,
    None,
]:
    settings = get_settings()
    yield RecipeIndexSyncService(
        session=session,
        recipes_path=settings.recipes_path,
    )
