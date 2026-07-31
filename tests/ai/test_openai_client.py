import asyncio
import json

import httpx
import pytest
from app.ai.exceptions import (
    AIAuthenticationError,
    AIRateLimitError,
    AITimeoutError,
)
from app.ai.openai_client import OpenAIClient


def _client(handler, *, max_retries: int = 0) -> OpenAIClient:
    return OpenAIClient(
        api_key="test-secret",
        model="gpt-5-nano",
        max_retries=max_retries,
        transport=httpx.MockTransport(handler),
    )


def _success_response() -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "choices": [
                {
                    "message": {
                        "content": json.dumps(
                            {
                                "title": "Soup",
                                "ingredients": [{"name": "water"}],
                                "instructions": ["Mix."],
                            }
                        ),
                        "refusal": None,
                    }
                }
            ]
        },
    )


def test_generate_json_uses_cheap_model_and_strict_schema() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-secret"
        payload = json.loads(request.content)
        assert payload["model"] == "gpt-5-nano"
        assert payload["reasoning_effort"] == "minimal"
        assert payload["max_completion_tokens"] == 8000
        assert payload["messages"][0]["content"] == [
            {"type": "text", "text": "Extract"}
        ]
        recipe_schema = payload["response_format"]["json_schema"]
        assert recipe_schema["strict"] is True
        assert recipe_schema["schema"]["additionalProperties"] is False
        assert set(recipe_schema["schema"]["required"]) == set(
            recipe_schema["schema"]["properties"]
        )
        return _success_response()

    result = asyncio.run(_client(handler).generate_json(prompt="Extract"))

    assert result["title"] == "Soup"


def test_generate_json_sends_original_image_as_data_url() -> None:
    image = b"\x89PNG\r\n\x1a\nimage"

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        image_content = payload["messages"][0]["content"][1]
        assert image_content["type"] == "image_url"
        assert image_content["image_url"]["url"].startswith("data:image/png;base64,")
        assert image_content["image_url"]["detail"] == "auto"
        return _success_response()

    asyncio.run(_client(handler).generate_json(prompt="Extract", images=[image]))


@pytest.mark.parametrize(
    ("status_code", "expected_error"),
    [
        (401, AIAuthenticationError),
        (403, AIAuthenticationError),
        (429, AIRateLimitError),
    ],
)
def test_generate_json_maps_provider_errors(
    status_code: int,
    expected_error: type[Exception],
) -> None:
    with pytest.raises(expected_error):
        asyncio.run(
            _client(
                lambda request: httpx.Response(status_code, json={"error": {}})
            ).generate_json(prompt="Extract")
        )


def test_generate_json_maps_timeout() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=request)

    with pytest.raises(AITimeoutError):
        asyncio.run(_client(handler).generate_json(prompt="Extract"))
