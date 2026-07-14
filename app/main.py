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