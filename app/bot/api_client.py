from dataclasses import dataclass
from typing import Any

import httpx


@dataclass(slots=True)
class RecipePreview:
    title: str
    servings: int | None
    prep_time_minutes: int | None
    cook_time_minutes: int | None
    total_time_minutes: int | None
    ingredient_count: int
    instruction_count: int
    source_url: str | None


@dataclass(slots=True)
class RecipeImportResponse:
    import_id: str
    status: str
    destination: str | None
    recipe: RecipePreview | None
    warnings: list[dict[str, Any]]


@dataclass(slots=True)
class RecipeDetail:
    identifier: str
    title: str
    ingredients: list[str]
    instructions: list[str]
    servings: int | None
    prep_time_minutes: int | None
    cook_time_minutes: int | None
    total_time_minutes: int | None
    source_url: str | None
    tags: list[str]
    meal_types: list[str]


def _parse_import_response(
    payload: dict[str, Any],
) -> RecipeImportResponse:
    recipe_payload = payload.get("recipe")
    recipe = None

    if recipe_payload is not None:
        recipe = RecipePreview(
            title=recipe_payload["title"],
            servings=recipe_payload.get("servings"),
            prep_time_minutes=recipe_payload.get("prep_time_minutes"),
            cook_time_minutes=recipe_payload.get("cook_time_minutes"),
            total_time_minutes=recipe_payload.get("total_time_minutes"),
            ingredient_count=recipe_payload["ingredient_count"],
            instruction_count=recipe_payload["instruction_count"],
            source_url=recipe_payload.get("source_url"),
        )

    return RecipeImportResponse(
        import_id=payload["import_id"],
        status=payload["status"],
        destination=payload.get("destination"),
        recipe=recipe,
        warnings=payload.get("warnings", []),
    )


@dataclass(slots=True)
class RecipeSearchResult:
    title: str
    path: str
    source_url: str | None


class RecipeApiClient:
    def __init__(
        self,
        base_url: str,
        timeout_seconds: float = 30.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    async def import_website_recipe(
        self,
        url: str,
        *,
        force: bool = False,
    ) -> RecipeImportResponse:
        endpoint = f"{self.base_url}/imports/website"

        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            transport=self.transport,
        ) as client:
            response = await client.post(
                endpoint,
                json={
                    "url": url,
                    "force": force,
                },
            )

        response.raise_for_status()

        return _parse_import_response(response.json())

    async def preview_website_recipe(
        self,
        url: str,
    ) -> RecipeImportResponse:
        endpoint = f"{self.base_url}/imports/website/preview"

        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            transport=self.transport,
        ) as client:
            response = await client.post(
                endpoint,
                json={
                    "url": url,
                    "force": False,
                },
            )

        response.raise_for_status()

        return _parse_import_response(response.json())

    async def preview_manual_recipe(
        self,
        text: str,
    ) -> RecipeImportResponse:
        endpoint = f"{self.base_url}/imports/manual/preview"

        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            transport=self.transport,
        ) as client:
            response = await client.post(
                endpoint,
                json={
                    "text": text,
                },
            )

        response.raise_for_status()

        return _parse_import_response(response.json())

    async def import_manual_recipe(
        self,
        text: str,
        *,
        force: bool = False,
    ) -> RecipeImportResponse:
        endpoint = f"{self.base_url}/imports/manual"

        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            transport=self.transport,
        ) as client:
            response = await client.post(
                endpoint,
                json={
                    "text": text,
                    "force": force,
                },
            )

        response.raise_for_status()

        return _parse_import_response(response.json())

    async def search_recipes(
        self,
        query: str,
        *,
        limit: int = 10,
    ) -> list[RecipeSearchResult]:
        endpoint = f"{self.base_url}/recipes/search"

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(
                endpoint,
                params={
                    "query": query,
                    "limit": limit,
                },
            )

        response.raise_for_status()

        payload = response.json()

        return [
            RecipeSearchResult(
                title=item["title"],
                path=item["path"],
                source_url=item.get("source_url"),
            )
            for item in payload
        ]

    async def get_recipe(
        self,
        identifier: str,
    ) -> RecipeDetail:
        endpoint = f"{self.base_url}/recipes/{identifier}"

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(endpoint)

        response.raise_for_status()

        payload = response.json()

        return RecipeDetail(
            identifier=payload["identifier"],
            title=payload["title"],
            ingredients=payload.get("ingredients", []),
            instructions=payload.get("instructions", []),
            servings=payload.get("servings"),
            prep_time_minutes=payload.get("prep_time_minutes"),
            cook_time_minutes=payload.get("cook_time_minutes"),
            total_time_minutes=payload.get("total_time_minutes"),
            source_url=payload.get("source_url"),
            tags=payload.get("tags", []),
            meal_types=payload.get("meal_types", []),
        )
