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
