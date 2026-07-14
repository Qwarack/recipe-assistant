import httpx
import pytest
from app.core.http_client import (
    HttpFetchError,
    ResponseTooLargeError,
    SafeHttpClient,
    UnsafeRedirectError,
)
from app.core.url_validation import UnsafeUrlError


def make_client(
    handler: httpx.MockTransport,
    *,
    max_response_bytes: int = 2_000_000,
    max_redirects: int = 3,
) -> SafeHttpClient:
    client = SafeHttpClient(
        max_response_bytes=max_response_bytes,
        max_redirects=max_redirects,
    )
    client._client.close()
    client._client = httpx.Client(
        transport=handler,
        follow_redirects=False,
    )
    return client


def test_get_text_returns_response_body(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.core.http_client.validate_public_http_url",
        lambda url: url,
    )

    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            text="<html>Recipe</html>",
            request=request,
        )
    )

    with make_client(transport) as client:
        result = client.get_text("https://example.com/recipe")

    assert result == "<html>Recipe</html>"


def test_http_error_is_wrapped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.core.http_client.validate_public_http_url",
        lambda url: url,
    )

    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            404,
            text="Not found",
            request=request,
        )
    )

    with (
        make_client(transport) as client,
        pytest.raises(
            HttpFetchError,
            match="HTTP 404",
        ),
    ):
        client.get_text("https://example.com/missing")


def test_large_response_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.core.http_client.validate_public_http_url",
        lambda url: url,
    )

    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            content=b"x" * 101,
            request=request,
        )
    )

    with (
        make_client(
            transport,
            max_response_bytes=100,
        ) as client,
        pytest.raises(ResponseTooLargeError),
    ):
        client.get_text("https://example.com/large")


def test_redirect_target_is_validated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def validate(url: str) -> str:
        if url == "http://127.0.0.1/internal":
            raise UnsafeUrlError("Unsafe URL")

        return url

    monkeypatch.setattr(
        "app.core.http_client.validate_public_http_url",
        validate,
    )

    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            302,
            headers={
                "location": "http://127.0.0.1/internal",
            },
            request=request,
        )
    )

    with make_client(transport) as client, pytest.raises(UnsafeRedirectError):
        client.get_text("https://example.com/recipe")


def test_too_many_redirects_are_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.core.http_client.validate_public_http_url",
        lambda url: url,
    )

    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            302,
            headers={
                "location": "/next",
            },
            request=request,
        )
    )

    with (
        make_client(
            transport,
            max_redirects=1,
        ) as client,
        pytest.raises(
            HttpFetchError,
            match="Maximum number of redirects exceeded",
        ),
    ):
        client.get_text("https://example.com/start")
