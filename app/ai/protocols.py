from typing import Any, Protocol


class JSONGenerator(Protocol):
    model: str
    provider: str
    uses_structured_outputs: bool

    async def generate_json(
        self,
        *,
        prompt: str,
        instructions: str | None = None,
        images: list[bytes] | None = None,
    ) -> dict[str, Any]: ...
