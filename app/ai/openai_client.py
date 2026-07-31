import asyncio
import base64
import json
import logging
from copy import deepcopy
from time import monotonic
from typing import Any

import httpx

from app.ai.exceptions import (
    AIAuthenticationError,
    AIInvalidResponseError,
    AIRateLimitError,
    AITimeoutError,
    AIUnavailableError,
)
from app.ai.schemas import AIRecipeResult

logger = logging.getLogger(__name__)

_openai_request_semaphore = asyncio.Semaphore(1)


class OpenAIClient:
    provider = "openai"
    uses_structured_outputs = True

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "gpt-5-nano",
        base_url: str = "https://api.openai.com/v1",
        timeout_seconds: float = 120.0,
        max_retries: int = 1,
        max_prompt_characters: int = 65_000,
        max_output_tokens: int = 8_000,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key.strip()
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(0, max_retries)
        self.max_prompt_characters = max_prompt_characters
        self.max_output_tokens = max_output_tokens
        self.transport = transport
        self.request_semaphore = _openai_request_semaphore

    async def generate_json(
        self,
        *,
        prompt: str,
        images: list[bytes] | None = None,
    ) -> dict[str, Any]:
        if not self.api_key:
            raise AIAuthenticationError("OPENAI_API_KEY is not configured")
        if not prompt.strip():
            raise AIInvalidResponseError("The AI prompt cannot be empty")
        if len(prompt) > self.max_prompt_characters:
            raise AIInvalidResponseError("The AI prompt exceeds the configured limit")

        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]
        for image in images or []:
            encoded = base64.b64encode(image).decode("ascii")
            content.append(
                {
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{_image_media_type(image)};base64,{encoded}",
                        "detail": "auto",
                    },
                }
            )

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": content}],
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "recipe",
                    "strict": True,
                    "schema": _strict_json_schema(AIRecipeResult.model_json_schema()),
                },
            },
            "reasoning_effort": "minimal",
            "max_completion_tokens": self.max_output_tokens,
        }
        started_at = monotonic()

        try:
            async with self.request_semaphore:
                response = await self._request_with_retry(payload)
            result = self._parse_chat_completion(response)
        except Exception as exc:
            logger.warning(
                "OpenAI recipe generation failed",
                extra={
                    "ai_provider": self.provider,
                    "ai_model": self.model,
                    "duration_ms": round((monotonic() - started_at) * 1000),
                    "success": False,
                    "error_code": type(exc).__name__,
                },
            )
            raise

        logger.info(
            "OpenAI recipe generation completed",
            extra={
                "ai_provider": self.provider,
                "ai_model": self.model,
                "duration_ms": round((monotonic() - started_at) * 1000),
                "success": True,
            },
        )
        return result

    async def _request_with_retry(self, payload: dict[str, Any]) -> httpx.Response:
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(self.timeout_seconds),
                    transport=self.transport,
                ) as client:
                    response = await client.post(
                        f"{self.base_url}/chat/completions",
                        headers={
                            "Authorization": f"Bearer {self.api_key}",
                            "Content-Type": "application/json",
                        },
                        json=payload,
                    )
            except httpx.TimeoutException as exc:
                if attempt < self.max_retries:
                    continue
                raise AITimeoutError("OpenAI request timed out") from exc
            except httpx.RequestError as exc:
                if attempt < self.max_retries:
                    continue
                raise AIUnavailableError("OpenAI is not reachable") from exc

            if response.status_code >= 500 and attempt < self.max_retries:
                continue

            self._raise_for_status(response)
            return response

        raise AIUnavailableError("OpenAI request could not be completed")

    @staticmethod
    def _raise_for_status(response: httpx.Response) -> None:
        if response.is_success:
            return
        if response.status_code in {401, 403}:
            raise AIAuthenticationError("OpenAI rejected the configured API key")
        if response.status_code == 429:
            raise AIRateLimitError("OpenAI rate limit or quota exceeded")
        raise AIUnavailableError(f"OpenAI returned HTTP {response.status_code}")

    @staticmethod
    def _parse_chat_completion(response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise AIInvalidResponseError(
                "OpenAI returned invalid response JSON"
            ) from exc

        try:
            message = payload["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise AIInvalidResponseError(
                "OpenAI returned no completion message"
            ) from exc

        refusal = message.get("refusal")
        if isinstance(refusal, str) and refusal.strip():
            raise AIInvalidResponseError("OpenAI refused to parse the recipe")

        raw_result = message.get("content")
        if not isinstance(raw_result, str) or not raw_result.strip():
            raise AIInvalidResponseError("OpenAI returned an empty model response")

        try:
            result = json.loads(raw_result)
        except json.JSONDecodeError as exc:
            raise AIInvalidResponseError(
                "The OpenAI response is not valid JSON"
            ) from exc

        if not isinstance(result, dict):
            raise AIInvalidResponseError("The OpenAI response must be a JSON object")
        return result


def _strict_json_schema(schema: dict[str, Any]) -> dict[str, Any]:
    strict = deepcopy(schema)

    def normalize(value: Any) -> None:
        if isinstance(value, dict):
            value.pop("default", None)
            properties = value.get("properties")
            if isinstance(properties, dict):
                value["required"] = list(properties)
                value["additionalProperties"] = False
            for child in value.values():
                normalize(child)
        elif isinstance(value, list):
            for child in value:
                normalize(child)

    normalize(strict)
    return strict


def _image_media_type(image: bytes) -> str:
    if image.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image.startswith(b"RIFF") and image[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"
