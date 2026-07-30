from functools import lru_cache
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import urlparse

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Recipe Assistant"
    app_version: str = "0.1.0"
    environment: str = "development"
    log_level: str = "INFO"
    recipes_path: Path = Path("data/recipes")
    database_path: Path = Path("data/database/app.db")
    imports_path: Path = Path("/data/imports")
    api_base_url: str = "http://127.0.0.1:8000"
    app_timezone: str = "Europe/Amsterdam"
    discord_allowed_role_ids: str | None = None
    ai_enabled: bool = True
    ollama_base_url: str = "http://ollama:11434"
    ollama_model: str = "gemma3:4b"
    ollama_timeout_seconds: float = 120.0
    ollama_max_retries: int = 1
    ai_enrich_missing_fields: bool = True
    ai_allow_ingredient_quantity_estimates: bool = False
    ai_allow_temperature_estimates: bool = False
    max_image_upload_bytes: int = 10 * 1024 * 1024
    max_image_dimension: int = 2048
    max_ai_source_characters: int = 50_000
    max_ai_prompt_characters: int = 65_000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    discord_bot_token: str | None = None
    discord_guild_id: int | None = None
    discord_allowed_channel_id: int | None = None

    @property
    def allowed_discord_role_ids(self) -> set[int]:
        if self.discord_allowed_role_ids is None:
            return set()

        return {
            int(role_id.strip())
            for role_id in self.discord_allowed_role_ids.split(",")
            if role_id.strip()
        }

    @field_validator("ollama_base_url")
    @classmethod
    def validate_local_ollama_url(cls, value: str) -> str:
        parsed = urlparse(value)
        hostname = parsed.hostname

        if (
            parsed.scheme not in {"http", "https"}
            or hostname is None
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("OLLAMA_BASE_URL must be a local HTTP(S) base URL")

        is_local_hostname = hostname == "localhost" or "." not in hostname

        try:
            address = ip_address(hostname)
        except ValueError:
            address = None

        if not is_local_hostname and (
            address is None or not (address.is_private or address.is_loopback)
        ):
            raise ValueError("OLLAMA_BASE_URL must point to a local Ollama service")

        return value.rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()
