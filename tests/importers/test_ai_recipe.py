import asyncio
from unittest.mock import AsyncMock

import pytest
from app.ai.exceptions import AIValidationError
from app.importers.ai_recipe import AIRecipeContext, AIRecipeImporter
from app.models.recipe import SourceType


def test_ai_importer_maps_valid_json_to_recipe() -> None:
    client = AsyncMock()
    client.model = "gemma3:4b"
    client.generate_json.return_value = {
        "title": "Tomatensoep",
        "servings": 4,
        "ingredients": [
            {
                "name": "tomaten",
                "quantity": 1,
                "unit": "kg",
            }
        ],
        "instructions": ["Snijd de tomaten.", "Kook de soep."],
        "cuisine": ["Nederlands"],
        "dietary": ["vegetarian"],
        "tags": ["soep"],
        "estimated_fields": ["servings"],
        "warnings": ["Porties zijn geschat."],
    }
    importer = AIRecipeImporter(client=client)

    result = asyncio.run(
        importer.import_text(
            "Tomatensoep",
            context=AIRecipeContext(source_type=SourceType.MANUAL),
        )
    )

    assert result.recipe.title == "Tomatensoep"
    assert result.recipe.extractor == "ollama:gemma3:4b"
    assert result.recipe.vegetarian is True
    assert result.recipe.tags == ["nederlands", "soep", "vegetarian"]
    assert result.estimated_fields == ["servings"]
    assert "servings" not in result.extracted_fields


def test_ai_importer_rejects_missing_required_recipe_fields() -> None:
    client = AsyncMock()
    client.model = "gemma3:4b"
    client.generate_json.return_value = {
        "title": "Geen recept",
        "ingredients": [],
        "instructions": [],
    }
    importer = AIRecipeImporter(client=client)

    with pytest.raises(AIValidationError, match="ingredients, instructions"):
        asyncio.run(
            importer.import_text(
                "Geen recept",
                context=AIRecipeContext(source_type=SourceType.MANUAL),
            )
        )


def test_ai_image_importer_passes_image_to_client() -> None:
    client = AsyncMock()
    client.model = "gemma3:4b"
    client.generate_json.return_value = {
        "title": "Pasta",
        "ingredients": [{"name": "pasta"}],
        "instructions": ["Kook de pasta."],
    }
    importer = AIRecipeImporter(client=client)

    asyncio.run(
        importer.import_image(
            b"image",
            context=AIRecipeContext(source_type=SourceType.IMAGE),
        )
    )

    assert client.generate_json.await_args.kwargs["images"] == [b"image"]
