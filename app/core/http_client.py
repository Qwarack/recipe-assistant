import logging
from collections.abc import Generator
from contextlib import contextmanager
from types import TracebackType

import httpx

from app.core.url_validation import UnsafeUrlError, validate_public_http_url

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_MAX_RESPONSE_BYTES = 2_000_000
DEFAULT_MAX_REDIRECTS = 3
DEFAULT_USER_AGENT = "RecipeAssistant/0.1"
DEFAULT_CHUNK_SIZE = 65_536


class HttpFetchError(RuntimeError):
    pass


class ResponseTooLargeError(HttpFetchError):
    pass


class UnsafeRedirectError(HttpFetchError):
    pass


class SafeHttpClient:
    def __init__(
        self,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
        max_redirects: int = DEFAULT_MAX_REDIRECTS,
        user_agent: str = DEFAULT_USER_AGENT,
    ) -> None:
        self.max_response_bytes = max_response_bytes
        self.max_redirects = max_redirects

        self._client = httpx.Client(
            timeout=httpx.Timeout(timeout_seconds),
            headers={
                "User-Agent": user_agent,
                "Accept": "text/html,application/xhtml+xml",
            },
            follow_redirects=False,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "SafeHttpClient":
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()

    def get_text(self, url: str) -> str:
        current_url = validate_public_http_url(url)

        for redirect_count in range(self.max_redirects + 1):
            with self._stream_request(current_url) as response:
                if response.is_redirect:
                    if redirect_count >= self.max_redirects:
                        raise HttpFetchError("Maximum number of redirects exceeded")

                    location = response.headers.get("location")

                    if not location:
                        raise HttpFetchError(
                            "Redirect response did not contain a Location header"
                        )

                    redirected_url = str(response.url.join(location))

                    try:
                        current_url = validate_public_http_url(redirected_url)
                    except UnsafeUrlError as exc:
                        raise UnsafeRedirectError(
                            "Redirect target is not allowed"
                        ) from exc

                    continue

                try:
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    raise HttpFetchError(
                        f"Remote server returned HTTP {response.status_code}"
                    ) from exc

                content = self._read_stream_limited(response)
                encoding = response.encoding or "utf-8"

                return content.decode(encoding, errors="replace")

        raise HttpFetchError("Request could not be completed")

    @contextmanager
    def _stream_request(
        self,
        url: str,
    ) -> Generator[httpx.Response, None, None]:
        logger.info("Fetching URL: %s", url)

        try:
            with self._client.stream("GET", url) as response:
                yield response
        except httpx.TimeoutException as exc:
            raise HttpFetchError("Request timed out") from exc
        except httpx.RequestError as exc:
            raise HttpFetchError("HTTP request failed") from exc

    def _read_stream_limited(self, response: httpx.Response) -> bytes:
        content_length = response.headers.get("content-length")

        if content_length is not None:
            try:
                declared_size = int(content_length)
            except ValueError:
                declared_size = None

            if declared_size is not None and declared_size > self.max_response_bytes:
                raise ResponseTooLargeError("Response exceeds the maximum allowed size")

        chunks: list[bytes] = []
        total_size = 0

        for chunk in response.iter_bytes(DEFAULT_CHUNK_SIZE):
            total_size += len(chunk)

            if total_size > self.max_response_bytes:
                raise ResponseTooLargeError("Response exceeds the maximum allowed size")

            chunks.append(chunk)

        return b"".join(chunks)
