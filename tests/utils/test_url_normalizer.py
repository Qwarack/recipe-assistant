from app.utils.url_normalizer import normalize_url


def test_normalizes_hostname_and_trailing_slash() -> None:
    result = normalize_url("HTTPS://EXAMPLE.COM/Pasta/")

    assert result == "https://example.com/Pasta"


def test_removes_fragment() -> None:
    result = normalize_url("https://example.com/pasta#ingredients")

    assert result == "https://example.com/pasta"


def test_removes_tracking_parameters() -> None:
    result = normalize_url(
        "https://example.com/pasta?utm_source=instagram&utm_campaign=dinner&servings=4"
    )

    assert result == ("https://example.com/pasta?servings=4")


def test_sorts_query_parameters() -> None:
    result = normalize_url("https://example.com/pasta?b=2&a=1")

    assert result == ("https://example.com/pasta?a=1&b=2")


def test_removes_default_https_port() -> None:
    result = normalize_url("https://example.com:443/pasta")

    assert result == "https://example.com/pasta"
