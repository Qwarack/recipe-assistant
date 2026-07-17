import asyncio
import json
from datetime import date

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


def test_preview_manual_recipe_uses_manual_preview_endpoint() -> None:
    recipe_text = "Soup\n\nIngrediënten:\n- water\n\nBereiding:\n1. Meng alles."

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url == "https://api.example.com/imports/manual/preview"
        assert json.loads(request.content) == {
            "text": recipe_text,
        }

        return httpx.Response(
            status_code=200,
            json={
                "import_id": "44444444-4444-4444-4444-444444444444",
                "status": "success",
                "destination": None,
                "recipe": None,
                "warnings": [],
            },
        )

    client = RecipeApiClient(
        base_url="https://api.example.com",
        transport=httpx.MockTransport(handler),
    )

    result = asyncio.run(client.preview_manual_recipe(recipe_text))

    assert result.destination is None


def test_import_manual_recipe_passes_force_flag() -> None:
    recipe_text = "Soup\n\nIngrediënten:\n- water\n\nBereiding:\n1. Meng alles."

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url == "https://api.example.com/imports/manual"
        assert json.loads(request.content) == {
            "text": recipe_text,
            "force": True,
        }

        return httpx.Response(
            status_code=201,
            json={
                "import_id": "55555555-5555-5555-5555-555555555555",
                "status": "success",
                "destination": "/data/recipes/soup.md",
                "recipe": None,
                "warnings": [],
            },
        )

    client = RecipeApiClient(
        base_url="https://api.example.com",
        transport=httpx.MockTransport(handler),
    )

    result = asyncio.run(
        client.import_manual_recipe(
            recipe_text,
            force=True,
        )
    )

    assert result.destination == "/data/recipes/soup.md"


def test_import_uploaded_recipe_sends_multipart_file_and_force_flag() -> None:
    content = b"# Pasta Carbonara"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/imports/upload"
        assert request.url.params["force"] == "true"
        assert request.headers["content-type"].startswith("multipart/form-data;")
        assert b"pasta.md" in request.content
        assert b"text/markdown" in request.content
        assert content in request.content

        return httpx.Response(
            status_code=200,
            json={
                "import_id": "66666666-6666-6666-6666-666666666666",
                "status": "success",
                "destination": "/data/recipes/pasta.md",
                "recipe": None,
                "warnings": [],
            },
        )

    client = RecipeApiClient(
        base_url="https://api.example.com",
        transport=httpx.MockTransport(handler),
    )

    result = asyncio.run(
        client.import_uploaded_recipe(
            filename="pasta.md",
            content=content,
            content_type="text/markdown",
            force=True,
        )
    )

    assert result.destination == "/data/recipes/pasta.md"


def test_get_current_meal_plan() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url == "http://api.test/meal-plans/current"

        return httpx.Response(
            status_code=200,
            json={
                "id": 10,
                "start_date": "2026-07-15",
                "end_date": "2026-07-21",
                "name": "Huidige planning",
                "entries": [
                    {
                        "id": 1,
                        "planned_date": "2026-07-17",
                        "meal_type": "dinner",
                        "servings": 2,
                        "notes": None,
                        "recipe_identifier": "pasta-carbonara",
                        "recipe_title": "Pasta Carbonara",
                    }
                ],
            },
        )

    client = RecipeApiClient(
        base_url="http://api.test",
        transport=httpx.MockTransport(handler),
    )

    result = asyncio.run(client.get_current_meal_plan())

    assert result.id == 10
    assert result.name == "Huidige planning"
    assert result.start_date == date(2026, 7, 15)
    assert result.entries[0].recipe_title == "Pasta Carbonara"


def test_update_meal_plan_entry_uses_patch_and_only_changed_fields() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "PATCH"
        assert request.url == "http://api.test/meal-plans/2026-07-15/entries/7"
        assert json.loads(request.content) == {
            "planned_date": "2026-07-18",
            "servings": 4,
            "notes": None,
        }
        return httpx.Response(
            200,
            json={
                "id": 10,
                "start_date": "2026-07-15",
                "end_date": "2026-07-21",
                "name": None,
                "entries": [],
            },
        )

    client = RecipeApiClient(
        base_url="http://api.test",
        transport=httpx.MockTransport(handler),
    )

    result = asyncio.run(
        client.update_meal_plan_entry(
            start_date=date(2026, 7, 15),
            entry_id=7,
            planned_date=date(2026, 7, 18),
            servings=4,
            notes=None,
            update_notes=True,
        )
    )

    assert result.id == 10


def test_remove_meal_plan_entry_uses_delete() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        assert request.url == "http://api.test/meal-plans/2026-07-15/entries/7"
        return httpx.Response(
            200,
            json={
                "id": 10,
                "start_date": "2026-07-15",
                "end_date": "2026-07-21",
                "name": None,
                "entries": [],
            },
        )

    client = RecipeApiClient(
        base_url="http://api.test",
        transport=httpx.MockTransport(handler),
    )

    result = asyncio.run(
        client.remove_meal_plan_entry(
            start_date=date(2026, 7, 15),
            entry_id=7,
        )
    )

    assert result.entries == []
