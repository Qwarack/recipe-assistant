import asyncio
import base64
import json
import logging
from time import monotonic
from typing import Any

import httpx

from app.ai.exceptions import (
    AIInvalidResponseError,
    AIModelNotFoundError,
    AITimeoutError,
    AIUnavailableError,
)

logger = logging.getLogger(__name__)

_ollama_request_semaphore = asyncio.Semaphore(1)


class OllamaClient:
    provider = "ollama"
    uses_structured_outputs = False

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        timeout_seconds: float = 120.0,
        max_retries: int = 1,
        max_prompt_characters: int = 65_000,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.max_retries = max(0, max_retries)
        self.max_prompt_characters = max_prompt_characters
        self.transport = transport
        self.request_semaphore = _ollama_request_semaphore

    async def generate_json(
        self,
        *,
        prompt: str,
        instructions: str | None = None,
        images: list[bytes] | None = None,
    ) -> dict[str, Any]:
        if not prompt.strip():
            raise AIInvalidResponseError("The AI prompt cannot be empty")

        if len(prompt) + len(instructions or "") > self.max_prompt_characters:
            raise AIInvalidResponseError("The AI prompt exceeds the configured limit")

        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "format": "json",
        }

        if instructions:
            payload["system"] = instructions

        if images:
            payload["images"] = [
                base64.b64encode(image).decode("ascii") for image in images
            ]

        started_at = monotonic()

        try:
            async with self.request_semaphore:
                response = await self._request_with_retry(payload)
            result = self._parse_generate_response(response)
        except Exception as exc:
            logger.warning(
                "Ollama JSON generation failed",
                extra={
                    "ai_model": self.model,
                    "duration_ms": round((monotonic() - started_at) * 1000),
                    "success": False,
                    "error_code": type(exc).__name__,
                },
            )
            raise

        logger.info(
            "Ollama JSON generation completed",
            extra={
                "ai_model": self.model,
                "duration_ms": round((monotonic() - started_at) * 1000),
                "success": True,
            },
        )
        return result

    async def healthcheck(self) -> bool:
        try:
            async with self._create_http_client() as client:
                response = await client.get(f"{self.base_url}/api/tags")
                response.raise_for_status()
        except (httpx.HTTPError, ValueError):
            return False

        return True

    async def _request_with_retry(
        self,
        payload: dict[str, Any],
    ) -> httpx.Response:
        for attempt in range(self.max_retries + 1):
            try:
                async with self._create_http_client() as client:
                    response = await client.post(
                        f"{self.base_url}/api/generate",
                        json=payload,
                    )
            except httpx.TimeoutException as exc:
                if attempt < self.max_retries:
                    continue
                raise AITimeoutError("Ollama request timed out") from exc
            except httpx.RequestError as exc:
                if attempt < self.max_retries:
                    continue
                raise AIUnavailableError("Ollama is not reachable") from exc

            if response.status_code >= 500 and attempt < self.max_retries:
                continue

            self._raise_for_status(response)
            return response

        raise AIUnavailableError("Ollama request could not be completed")

    def _create_http_client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            timeout=httpx.Timeout(self.timeout_seconds),
            transport=self.transport,
        )

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.is_success:
            return

        error_message = self._read_error_message(response)
        normalized_error = error_message.casefold()

        if response.status_code == 404 or (
            "model" in normalized_error
            and any(
                marker in normalized_error
                for marker in ("not found", "missing", "pull")
            )
        ):
            raise AIModelNotFoundError(
                f"The configured Ollama model {self.model!r} is not installed"
            )

        raise AIUnavailableError(f"Ollama returned HTTP {response.status_code}")

    @staticmethod
    def _read_error_message(response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return response.text

        if isinstance(payload, dict) and isinstance(payload.get("error"), str):
            return payload["error"]

        return response.text

    @staticmethod
    def _parse_generate_response(response: httpx.Response) -> dict[str, Any]:
        try:
            payload = response.json()
        except ValueError as exc:
            raise AIInvalidResponseError(
                "Ollama returned invalid response JSON"
            ) from exc

        raw_result = payload.get("response") if isinstance(payload, dict) else None

        if not isinstance(raw_result, str) or not raw_result.strip():
            raise AIInvalidResponseError("Ollama returned an empty model response")

        try:
            result = json.loads(raw_result)
        except json.JSONDecodeError as exc:
            raise AIInvalidResponseError(
                "The model response is not valid JSON"
            ) from exc

        if not isinstance(result, dict):
            raise AIInvalidResponseError("The model response must be a JSON object")

        return result
