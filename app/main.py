import logging

from fastapi import FastAPI

from app.core.config import get_settings
from app.core.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)

logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
)


@app.on_event("startup")
def startup_event() -> None:
    logger.info(
        "Starting %s version %s in %s mode",
        settings.app_name,
        settings.app_version,
        settings.environment,
    )


@app.get("/")
def root() -> dict[str, str]:
    logger.info("Root endpoint requested")

    return {
        "message": f"{settings.app_name} is running",
        "environment": settings.environment,
    }

@app.get("/storage-test")
def storage_test() -> dict[str, str]:
    settings.recipes_path.mkdir(parents=True, exist_ok=True)

    test_file = settings.recipes_path / "test-recipe.md"
    test_file.write_text(
        "# Test recipe\n\nPersistent storage works.\n",
        encoding="utf-8",
    )

    logger.info("Created storage test file at %s", test_file)

    return {
        "message": "Test file created",
        "path": str(test_file),
    }

@app.get("/database-storage-test")
def database_storage_test() -> dict[str, str]:
    settings.database_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    settings.database_path.touch(exist_ok=True)

    logger.info(
        "Database storage test file created at %s",
        settings.database_path,
    )

    return {
        "message": "Database storage is available",
        "path": str(settings.database_path),
    }