import pytest
from app.core.config import Settings


def test_allowed_discord_role_ids_parses_comma_separated_values() -> None:
    settings = Settings(
        _env_file=None,
        discord_allowed_role_ids="111, 222,333",
    )

    assert settings.allowed_discord_role_ids == {111, 222, 333}


def test_allowed_discord_role_ids_is_empty_when_not_configured() -> None:
    settings = Settings(
        _env_file=None,
        discord_allowed_role_ids=None,
    )

    assert settings.allowed_discord_role_ids == set()


def test_default_application_timezone_is_amsterdam() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_timezone == "Europe/Amsterdam"


def test_openai_fallback_requires_non_empty_api_key() -> None:
    assert Settings(_env_file=None, openai_api_key=None).openai_configured is False
    assert Settings(_env_file=None, openai_api_key="").openai_configured is False
    assert Settings(_env_file=None, openai_api_key="sk-test").openai_configured is True


def test_openai_base_url_must_use_official_api_host() -> None:
    with pytest.raises(ValueError, match="OPENAI_BASE_URL"):
        Settings(
            _env_file=None,
            openai_api_key="sk-test",
            openai_base_url="https://example.com/v1",
        )


def test_confidence_thresholds_must_be_ordered() -> None:
    with pytest.raises(ValueError, match="retry < warning < high"):
        Settings(
            _env_file=None,
            ai_confidence_retry_threshold=0.85,
            ai_confidence_warning_threshold=0.80,
            ai_confidence_high_threshold=0.95,
        )
