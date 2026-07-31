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


def test_ai_importer_keeps_recipe_with_invalid_estimated_field() -> None:
    client = AsyncMock()
    client.model = "gpt-5-nano"
    client.provider = "openai"
    client.uses_structured_outputs = True
    client.generate_json.return_value = {
        "title": "ROMEINS PIZZADEEG",
        "description": None,
        "servings": None,
        "prep_time_minutes": 15,
        "cook_time_minutes": None,
        "total_time_minutes": None,
        "ingredients": [
            {"name": "bloem", "quantity": 550, "unit": "g"},
            {"name": "gist", "quantity": 10, "unit": "g"},
            {"name": "water", "quantity": 360, "unit": "ml"},
            {"name": "zout", "quantity": 12, "unit": "g"},
            {"name": "olijfolie", "quantity": 2, "unit": "el"},
        ],
        "instructions": [
            "Meng de bloem met de gist en het water.",
            "Voeg zout en olijfolie toe en kneed het deeg.",
            "Laat het deeg rijzen.",
        ],
        "cuisine": ["Dutch"],
        "meal_types": ["dinner"],
        "dietary": [],
        "tags": ["pizza", "dough"],
        "difficulty": None,
        "warnings": ["De bron bevat mogelijk onduidelijke tekst."],
        "estimated_fields": [
            "title",
            "ingredients",
            "instructions",
            "prep_time_minutes",
            "meal_types",
            "warnings",
        ],
        "confidence": 0.42,
        "confidence_reasons": ["De OCR was niet overal duidelijk."],
    }
    importer = AIRecipeImporter(client=client)

    result = asyncio.run(
        importer.import_image(
            b"image",
            context=AIRecipeContext(source_type=SourceType.IMAGE),
        )
    )

    assert result.recipe.title == "ROMEINS PIZZADEEG"
    assert len(result.recipe.ingredients) == 5
    assert len(result.recipe.instructions) == 3
    assert "warnings" not in result.estimated_fields
    assert result.confidence == 0.42
    assert any("bruikbare recept is behouden" in warning for warning in result.warnings)
    assert any(
        "automatisch gecorrigeerd" in reason for reason in result.confidence_reasons
    )


def test_ai_importer_repairs_invalid_optional_metadata_but_requires_review() -> None:
    client = AsyncMock()
    client.model = "qwen3.5:4b"
    client.provider = "ollama"
    client.uses_structured_outputs = False
    client.generate_json.return_value = {
        "title": "Langzaam deeg",
        "servings": 0,
        "ingredients": {"name": "bloem", "quantity": 550, "unit": "g"},
        "instructions": "Meng en kneed het deeg.",
        "meal_types": ["dinner", "supper"],
        "difficulty": "unknown",
        "confidence": 1.5,
        "estimated_fields": "meal_types",
        "unexpected_note": "ignore me",
    }
    importer = AIRecipeImporter(client=client)

    result = asyncio.run(
        importer.import_text(
            "Langzaam deeg",
            context=AIRecipeContext(source_type=SourceType.MANUAL),
        )
    )

    assert result.recipe.title == "Langzaam deeg"
    assert [ingredient.name for ingredient in result.recipe.ingredients] == ["bloem"]
    assert result.recipe.instructions == ["Meng en kneed het deeg."]
    assert result.recipe.servings is None
    assert result.recipe.meal_types == ["dinner"]
    assert result.recipe.difficulty == "unknown"
    assert result.estimated_fields == ["meal_types"]
    assert result.confidence == 0.90
    assert result.warnings


def test_ai_importer_does_not_repair_invalid_recipe_core() -> None:
    client = AsyncMock()
    client.model = "qwen3.5:4b"
    client.provider = "ollama"
    client.generate_json.return_value = {
        "title": "Beschadigd recept",
        "ingredients": [{"unit": "g"}],
        "instructions": ["Meng alles."],
        "estimated_fields": ["warnings"],
    }
    importer = AIRecipeImporter(client=client)

    with pytest.raises(AIValidationError, match="recipe schema"):
        asyncio.run(
            importer.import_text(
                "Beschadigd recept",
                context=AIRecipeContext(source_type=SourceType.MANUAL),
            )
        )


def test_ai_importer_keeps_named_ingredient_with_invalid_optional_details() -> None:
    client = AsyncMock()
    client.model = "qwen3.5:4b"
    client.provider = "ollama"
    client.generate_json.return_value = {
        "title": "Pizzadeeg",
        "ingredients": [
            {
                "name": "bloem",
                "quantity": -550,
                "unit": "g",
                "confidence": "unsupported ingredient field",
            }
        ],
        "instructions": ["Kneed het deeg."],
    }
    importer = AIRecipeImporter(client=client)

    result = asyncio.run(
        importer.import_text(
            "Pizzadeeg",
            context=AIRecipeContext(source_type=SourceType.MANUAL),
        )
    )

    assert len(result.recipe.ingredients) == 1
    assert result.recipe.ingredients[0].name == "bloem"
    assert result.recipe.ingredients[0].quantity is None
    assert result.recipe.ingredients[0].unit == "g"
    assert result.confidence == 0.90
    assert result.warnings


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
