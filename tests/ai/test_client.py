import asyncio
import base64
import json

import httpx
import pytest
from app.ai.client import OllamaClient
from app.ai.exceptions import (
    AIInvalidResponseError,
    AIModelNotFoundError,
    AITimeoutError,
    AIUnavailableError,
)


def _client(handler, *, max_retries: int = 0) -> OllamaClient:
    return OllamaClient(
        base_url="http://ollama:11434",
        model="gemma3:4b",
        max_retries=max_retries,
        transport=httpx.MockTransport(handler),
    )


def test_generate_json_returns_parsed_model_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["model"] == "gemma3:4b"
        assert payload["format"] == "json"
        assert payload["stream"] is False
        return httpx.Response(200, json={"response": '{"title":"Soup"}'})

    result = asyncio.run(_client(handler).generate_json(prompt="Extract"))

    assert result == {"title": "Soup"}


def test_generate_json_sends_base64_images() -> None:
    image = b"fake-image"

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        assert payload["images"] == [
            base64.b64encode(image).decode("ascii"),
        ]
        return httpx.Response(200, json={"response": "{}"})

    asyncio.run(_client(handler).generate_json(prompt="Extract", images=[image]))


@pytest.mark.parametrize(
    "response",
    [
        httpx.Response(200, json={"response": ""}),
        httpx.Response(200, json={"response": "not-json"}),
        httpx.Response(200, content=b"not-json"),
    ],
)
def test_generate_json_rejects_invalid_or_empty_output(
    response: httpx.Response,
) -> None:
    with pytest.raises(AIInvalidResponseError):
        asyncio.run(_client(lambda request: response).generate_json(prompt="Extract"))


def test_generate_json_maps_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(AITimeoutError):
        asyncio.run(_client(handler).generate_json(prompt="Extract"))


def test_generate_json_maps_missing_model() -> None:
    response = httpx.Response(
        404,
        json={"error": "model 'gemma3:4b' not found, try pulling it first"},
    )

    with pytest.raises(AIModelNotFoundError):
        asyncio.run(_client(lambda request: response).generate_json(prompt="Extract"))


def test_generate_json_retries_temporary_server_error() -> None:
    attempts = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            return httpx.Response(500, json={"error": "temporary"})
        return httpx.Response(200, json={"response": "{}"})

    result = asyncio.run(
        _client(handler, max_retries=1).generate_json(prompt="Extract")
    )

    assert result == {}
    assert attempts == 2


def test_generate_json_maps_http_500() -> None:
    with pytest.raises(AIUnavailableError):
        asyncio.run(
            _client(
                lambda request: httpx.Response(500, json={"error": "broken"})
            ).generate_json(prompt="Extract")
        )


def test_healthcheck_returns_false_when_ollama_is_down() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("offline", request=request)

    assert asyncio.run(_client(handler).healthcheck()) is False
