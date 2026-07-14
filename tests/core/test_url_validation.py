import pytest
from app.core.url_validation import UnsafeUrlError, validate_public_http_url


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com/recipe",
        "http://example.com",
        "https://8.8.8.8",
    ],
)
def test_public_http_urls_are_allowed(url: str) -> None:
    assert validate_public_http_url(url) == url


@pytest.mark.parametrize(
    "url",
    [
        "ftp://example.com/file",
        "file:///etc/passwd",
        "mailto:test@example.com",
        "example.com/recipe",
    ],
)
def test_non_http_urls_are_rejected(url: str) -> None:
    with pytest.raises(UnsafeUrlError):
        validate_public_http_url(url)


@pytest.mark.parametrize(
    "url",
    [
        "http://localhost",
        "http://api.localhost",
        "http://127.0.0.1",
        "http://10.0.0.1",
        "http://192.168.1.1",
        "http://172.16.0.1",
        "http://169.254.169.254",
        "http://[::1]",
    ],
)
def test_local_and_private_urls_are_rejected(url: str) -> None:
    with pytest.raises(UnsafeUrlError):
        validate_public_http_url(url)


def test_url_without_hostname_is_rejected() -> None:
    with pytest.raises(UnsafeUrlError):
        validate_public_http_url("https:///recipe")
