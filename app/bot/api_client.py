from dataclasses import dataclass
from datetime import date
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


@dataclass(slots=True)
class MealPlanEntry:
    id: int
    planned_date: date
    meal_type: str
    servings: int
    notes: str | None
    recipe_identifier: str
    recipe_title: str


@dataclass(slots=True)
class MealPlan:
    id: int
    start_date: date
    end_date: date
    name: str | None
    entries: list[MealPlanEntry]


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
    identifier: str
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

        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            transport=self.transport,
        ) as client:
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
                identifier=item["identifier"],
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

    async def delete_recipe(
        self,
        identifier: str,
    ) -> None:
        endpoint = f"{self.base_url}/recipes/{identifier}"

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.delete(endpoint)

        response.raise_for_status()

    async def preview_uploaded_recipe(
        self,
        *,
        filename: str,
        content: bytes,
        content_type: str | None = None,
    ) -> RecipeImportResponse:
        endpoint = f"{self.base_url}/imports/upload/preview"

        files = {
            "file": (
                filename,
                content,
                content_type or "application/octet-stream",
            )
        }

        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            transport=self.transport,
        ) as client:
            response = await client.post(
                endpoint,
                files=files,
            )

        response.raise_for_status()

        return _parse_import_response(response.json())

    async def import_uploaded_recipe(
        self,
        *,
        filename: str,
        content: bytes,
        content_type: str | None = None,
        force: bool = False,
    ) -> RecipeImportResponse:
        endpoint = f"{self.base_url}/imports/upload"

        files = {
            "file": (
                filename,
                content,
                content_type or "application/octet-stream",
            )
        }

        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            transport=self.transport,
        ) as client:
            response = await client.post(
                endpoint,
                params={
                    "force": force,
                },
                files=files,
            )

        response.raise_for_status()

        return _parse_import_response(response.json())

    async def get_meal_plan(
        self,
        start_date: date,
    ) -> MealPlan:
        endpoint = f"{self.base_url}/meal-plans/{start_date.isoformat()}"

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(endpoint)

        response.raise_for_status()

        return _parse_meal_plan(response.json())

    async def get_current_meal_plan(
        self,
    ) -> MealPlan:
        endpoint = f"{self.base_url}/meal-plans/current"

        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            transport=self.transport,
        ) as client:
            response = await client.get(endpoint)

        response.raise_for_status()

        return _parse_meal_plan(response.json())

    async def add_meal_plan_entry(
        self,
        *,
        start_date: date,
        planned_date: date,
        recipe_identifier: str,
        meal_type: str = "dinner",
        servings: int = 2,
        notes: str | None = None,
        plan_name: str | None = None,
    ) -> MealPlan:
        endpoint = f"{self.base_url}/meal-plans/{start_date.isoformat()}/entries"

        response_payload = {
            "planned_date": planned_date.isoformat(),
            "recipe_identifier": recipe_identifier,
            "meal_type": meal_type,
            "servings": servings,
            "notes": notes,
            "plan_name": plan_name,
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(
                endpoint,
                json=response_payload,
            )

        response.raise_for_status()

        return _parse_meal_plan(response.json())


def _parse_meal_plan(
    payload: dict[str, Any],
) -> MealPlan:
    entries = [
        MealPlanEntry(
            id=item["id"],
            planned_date=date.fromisoformat(item["planned_date"]),
            meal_type=item["meal_type"],
            servings=item["servings"],
            notes=item.get("notes"),
            recipe_identifier=item["recipe_identifier"],
            recipe_title=item["recipe_title"],
        )
        for item in payload.get("entries", [])
    ]

    return MealPlan(
        id=payload["id"],
        start_date=date.fromisoformat(payload["start_date"]),
        end_date=date.fromisoformat(payload["end_date"]),
        name=payload.get("name"),
        entries=entries,
    )
