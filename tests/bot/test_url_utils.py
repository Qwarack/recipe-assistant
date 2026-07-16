from app.bot.url_utils import extract_first_url


def test_extracts_url_from_message() -> None:
    result = extract_first_url("Probeer dit recept: https://example.com/pasta")

    assert result == "https://example.com/pasta"


def test_removes_trailing_punctuation() -> None:
    result = extract_first_url("Deze lijkt lekker: https://example.com/soup.")

    assert result == "https://example.com/soup"


def test_returns_first_url() -> None:
    result = extract_first_url(
        "Eerste: https://example.com/one tweede: https://example.com/two"
    )

    assert result == "https://example.com/one"


def test_returns_none_without_url() -> None:
    assert extract_first_url("Geen link aanwezig") is None


def test_ignores_non_http_url() -> None:
    assert extract_first_url("ftp://example.com/recipe") is None
