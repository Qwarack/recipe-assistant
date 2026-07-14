import socket
from unittest.mock import patch

import pytest
from app.core.url_validation import UnsafeUrlError, validate_public_http_url


@pytest.mark.parametrize(
    "url",
    [
        "https://8.8.8.8",
        "http://1.1.1.1",
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


def test_hostname_resolving_to_public_ip_is_allowed() -> None:
    fake_address_info = [
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            6,
            "",
            ("93.184.216.34", 0),
        )
    ]

    with patch(
        "app.core.url_validation.socket.getaddrinfo",
        return_value=fake_address_info,
    ):
        result = validate_public_http_url("https://recipes.example.com/pasta")

    assert result == "https://recipes.example.com/pasta"


@pytest.mark.parametrize(
    "private_ip",
    [
        "127.0.0.1",
        "10.0.0.1",
        "192.168.1.10",
        "169.254.169.254",
        "::1",
    ],
)
def test_hostname_resolving_to_private_ip_is_rejected(
    private_ip: str,
) -> None:
    address_family = socket.AF_INET6 if ":" in private_ip else socket.AF_INET

    fake_address_info = [
        (
            address_family,
            socket.SOCK_STREAM,
            6,
            "",
            (private_ip, 0),
        )
    ]

    with (
        patch(
            "app.core.url_validation.socket.getaddrinfo",
            return_value=fake_address_info,
        ),
        pytest.raises(UnsafeUrlError),
    ):
        validate_public_http_url("https://evil.example.com/recipe")


def test_hostname_with_mixed_public_and_private_ips_is_rejected() -> None:
    fake_address_info = [
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            6,
            "",
            ("93.184.216.34", 0),
        ),
        (
            socket.AF_INET,
            socket.SOCK_STREAM,
            6,
            "",
            ("127.0.0.1", 0),
        ),
    ]

    with (
        patch(
            "app.core.url_validation.socket.getaddrinfo",
            return_value=fake_address_info,
        ),
        pytest.raises(UnsafeUrlError),
    ):
        validate_public_http_url("https://mixed.example.com/recipe")


def test_unresolvable_hostname_is_rejected() -> None:
    with (
        patch(
            "app.core.url_validation.socket.getaddrinfo",
            side_effect=socket.gaierror,
        ),
        pytest.raises(
            UnsafeUrlError,
            match="Hostname could not be resolved",
        ),
    ):
        validate_public_http_url("https://missing.example.com/recipe")
