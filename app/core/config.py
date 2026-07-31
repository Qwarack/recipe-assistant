from functools import lru_cache
from ipaddress import ip_address
from pathlib import Path
from typing import Self
from urllib.parse import urlparse

from pydantic import Field, SecretStr, field_validator, model_validator
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
    ollama_model: str = "qwen3.5:4b"
    ollama_timeout_seconds: float = 120.0
    ollama_max_retries: int = 1
    openai_fallback_enabled: bool = True
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-5-nano"
    openai_base_url: str = "https://api.openai.com/v1"
    openai_timeout_seconds: float = 120.0
    openai_max_retries: int = 1
    openai_max_output_tokens: int = 8_000
    ai_enrich_missing_fields: bool = True
    ai_allow_ingredient_quantity_estimates: bool = False
    ai_allow_temperature_estimates: bool = False
    ai_confidence_high_threshold: float = Field(default=0.95, ge=0, le=1)
    ai_confidence_warning_threshold: float = Field(default=0.80, ge=0, le=1)
    ai_confidence_retry_threshold: float = Field(default=0.60, ge=0, le=1)
    ai_confidence_max_local_retries: int = Field(default=1, ge=0, le=5)
    recipe_index_auto_sync: bool = True
    recipe_index_sync_interval_seconds: float = Field(default=2.0, ge=0.5, le=3600)
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

    @property
    def openai_configured(self) -> bool:
        return bool(
            self.ai_enabled
            and self.openai_fallback_enabled
            and self.openai_api_key is not None
            and self.openai_api_key.get_secret_value().strip()
        )

    @model_validator(mode="after")
    def validate_confidence_thresholds(self) -> Self:
        if not (
            self.ai_confidence_retry_threshold
            < self.ai_confidence_warning_threshold
            < self.ai_confidence_high_threshold
        ):
            raise ValueError(
                "AI confidence thresholds must satisfy retry < warning < high"
            )
        return self

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

    @field_validator("openai_base_url")
    @classmethod
    def validate_openai_url(cls, value: str) -> str:
        parsed = urlparse(value)
        if (
            parsed.scheme != "https"
            or parsed.hostname != "api.openai.com"
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError(
                "OPENAI_BASE_URL must use the official https://api.openai.com host"
            )
        return value.rstrip("/")


@lru_cache
def get_settings() -> Settings:
    return Settings()
