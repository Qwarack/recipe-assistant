from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Recipe Assistant"
    app_version: str = "0.1.0"
    environment: str = "development"
    log_level: str = "INFO"
    recipes_path: Path = Path("data/recipes")
    database_path: Path = Path("data/database/recipes.db")
    imports_path: Path = Path("/data/imports")
    api_base_url: str = "http://127.0.0.1:8000"
    discord_allowed_role_ids: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    discord_bot_token: str | None = None
    discord_guild_id: int | None = None
    discord_allowed_channel_id: int | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
