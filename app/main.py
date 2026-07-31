import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from app.api.ai_imports import router as ai_imports_router
from app.api.health import router as health_router
from app.api.imports import router as imports_router
from app.api.meal_plans import router as meal_plans_router
from app.api.search import router as search_router
from app.api.uploads import router as uploads_router
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.database.engine import create_session_factory
from app.services.recipe_index_watcher import RecipeIndexWatcher

settings = get_settings()
configure_logging(settings.log_level)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info(
        "Starting %s version %s in %s mode",
        settings.app_name,
        settings.app_version,
        settings.environment,
    )

    watcher_task: asyncio.Task[None] | None = None
    if settings.recipe_index_auto_sync:
        watcher = RecipeIndexWatcher(
            session_factory=create_session_factory(settings.database_path),
            recipes_path=settings.recipes_path,
            interval_seconds=settings.recipe_index_sync_interval_seconds,
        )
        watcher_task = asyncio.create_task(
            watcher.run(),
            name="recipe-index-watcher",
        )

    try:
        yield
    finally:
        if watcher_task is not None:
            watcher_task.cancel()
            with suppress(asyncio.CancelledError):
                await watcher_task

    logger.info("Shutting down %s", settings.app_name)


app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    lifespan=lifespan,
)

app.include_router(health_router)
app.include_router(imports_router)
app.include_router(ai_imports_router)
app.include_router(meal_plans_router)
app.include_router(search_router)
app.include_router(uploads_router)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": f"{settings.app_name} is running",
        "environment": settings.environment,
    }
