import asyncio
import json

import httpx
from app.bot.api_client import RecipeApiClient


def test_import_website_recipe_maps_request_and_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url == "https://api.example.com/imports/website"
        assert json.loads(request.content) == {
            "url": "https://example.com/soup",
            "force": True,
        }

        return httpx.Response(
            status_code=201,
            json={
                "import_id": "11111111-1111-1111-1111-111111111111",
                "status": "success",
                "destination": "/data/recipes/soup.md",
                "recipe": {
                    "title": "Soup",
                    "servings": 4,
                    "prep_time_minutes": 10,
                    "cook_time_minutes": 20,
                    "total_time_minutes": 30,
                    "ingredient_count": 2,
                    "instruction_count": 1,
                    "source_url": "https://example.com/soup",
                },
                "warnings": [],
            },
        )

    client = RecipeApiClient(
        base_url="https://api.example.com/",
        transport=httpx.MockTransport(handler),
    )

    result = asyncio.run(
        client.import_website_recipe(
            "https://example.com/soup",
            force=True,
        )
    )

    assert result.import_id == "11111111-1111-1111-1111-111111111111"
    assert result.status == "success"
    assert result.destination == "/data/recipes/soup.md"
    assert result.recipe is not None
    assert result.recipe.title == "Soup"
    assert result.recipe.ingredient_count == 2
    assert result.recipe.instruction_count == 1
    assert result.warnings == []


def test_import_website_recipe_accepts_response_without_recipe() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=201,
            json={
                "import_id": "22222222-2222-2222-2222-222222222222",
                "status": "partial",
                "destination": None,
            },
        )

    client = RecipeApiClient(
        base_url="https://api.example.com",
        transport=httpx.MockTransport(handler),
    )

    result = asyncio.run(client.import_website_recipe("https://example.com/soup"))

    assert result.recipe is None
    assert result.warnings == []


def test_preview_website_recipe_uses_preview_endpoint() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url == "https://api.example.com/imports/website/preview"
        assert json.loads(request.content) == {
            "url": "https://example.com/pasta",
            "force": False,
        }

        return httpx.Response(
            status_code=200,
            json={
                "import_id": "33333333-3333-3333-3333-333333333333",
                "status": "success",
                "destination": None,
                "recipe": {
                    "title": "Pasta",
                    "servings": None,
                    "prep_time_minutes": None,
                    "cook_time_minutes": None,
                    "total_time_minutes": None,
                    "ingredient_count": 1,
                    "instruction_count": 1,
                    "source_url": "https://example.com/pasta",
                },
                "warnings": [],
            },
        )

    client = RecipeApiClient(
        base_url="https://api.example.com",
        transport=httpx.MockTransport(handler),
    )

    result = asyncio.run(client.preview_website_recipe("https://example.com/pasta"))

    assert result.destination is None
    assert result.recipe is not None
    assert result.recipe.title == "Pasta"
