import asyncio
from unittest.mock import AsyncMock

import pytest
from app.ai.exceptions import AIValidationError
from app.importers.ai_recipe import AIRecipeContext, AIRecipeImporter
from app.models.recipe import SourceType


def test_ai_importer_maps_valid_json_to_recipe() -> None:
    client = AsyncMock()
    client.model = "qwen3.5:4b"
    client.provider = "ollama"
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
        "confidence": 0.72,
        "confidence_reasons": ["Porties ontbreken in de bron."],
    }
    importer = AIRecipeImporter(client=client)

    result = asyncio.run(
        importer.import_text(
            "Tomatensoep",
            context=AIRecipeContext(source_type=SourceType.MANUAL),
        )
    )

    assert result.recipe.title == "Tomatensoep"
    assert result.recipe.extractor == "ollama:qwen3.5:4b"
    assert result.recipe.vegetarian is True
    assert result.recipe.tags == ["nederlands", "soep", "vegetarian"]
    assert result.estimated_fields == ["servings"]
    assert "servings" not in result.extracted_fields
    assert result.confidence == 0.72
    assert result.confidence_reasons == ["Porties ontbreken in de bron."]


def test_structured_output_client_does_not_duplicate_schema_in_prompt() -> None:
    client = AsyncMock()
    client.model = "gpt-5-nano"
    client.provider = "openai"
    client.uses_structured_outputs = True
    client.generate_json.return_value = {
        "title": "Soep",
        "ingredients": [{"name": "water"}],
        "instructions": ["Meng."],
    }
    importer = AIRecipeImporter(client=client)

    asyncio.run(
        importer.import_text(
            "Soep met water",
            context=AIRecipeContext(source_type=SourceType.MANUAL),
        )
    )

    prompt = client.generate_json.await_args.kwargs["prompt"]
    instructions = client.generate_json.await_args.kwargs["instructions"]
    assert "Soep met water" in prompt
    assert "provided strict structured-output contract" in instructions
    assert '"properties"' not in instructions


def test_ai_prompt_contains_targeted_normalization_examples() -> None:
    client = AsyncMock()
    client.model = "gpt-5-nano"
    client.provider = "openai"
    client.uses_structured_outputs = True
    client.generate_json.return_value = {
        "title": "Pasta",
        "ingredients": [{"name": "pasta"}],
        "instructions": ["Kook de pasta."],
    }
    importer = AIRecipeImporter(client=client)

    asyncio.run(
        importer.import_text(
            "1. Kook 400 gram pasta.",
            context=AIRecipeContext(source_type=SourceType.MANUAL),
        )
    )

    instructions = client.generate_json.await_args.kwargs["instructions"]
    prompt = client.generate_json.await_args.kwargs["prompt"]
    assert "Never include leading step" in instructions
    assert "numbers, bullets" in instructions
    assert "`400 gram pasta`" in instructions
    assert "A beverage is not dinner" in instructions
    assert "<recipe_source>" in prompt


def test_ai_importer_rejects_missing_required_recipe_fields() -> None:
    client = AsyncMock()
    client.model = "qwen3.5:4b"
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
    client.model = "qwen3.5:4b"
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
