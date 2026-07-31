import asyncio
from unittest.mock import AsyncMock

import pytest
from app.ai.exceptions import AIUnavailableError
from app.importers.ai_recipe import AIRecipeImport
from app.models.import_result import ImportResult, ImportStatus
from app.models.import_session import (
    AIParseReason,
    ImportProcessingStatus,
    ImportSource,
    ParseMethod,
)
from app.models.recipe import Ingredient, Recipe, SourceType
from app.services.ai_import_orchestrator import AIImportOrchestrator
from app.services.import_session_repository import ImportSessionRepository
from app.services.recipe_enrichment_service import EnrichmentResult


def _recipe(title: str = "Normal soup") -> Recipe:
    return Recipe(
        title=title,
        source_type=SourceType.MANUAL,
        servings=4,
        prep_time_minutes=10,
        cook_time_minutes=20,
        difficulty="easy",
        ingredients=[Ingredient(name="water", quantity=1, unit="l")],
        instructions=["Mix."],
        tags=["soup"],
        meal_types=["dinner"],
    )


def _orchestrator(
    *,
    importer,
    repository: ImportSessionRepository,
) -> AIImportOrchestrator:
    enrichment = AsyncMock()
    loader = AsyncMock()
    loader.load_text.return_value = "Original source"
    return AIImportOrchestrator(
        repository=repository,
        importer=importer,
        enrichment_service=enrichment,
        source_loader=loader,
        ai_model="qwen3.5:4b",
        enrich_missing_fields=False,
    )


def test_ai_reparse_replaces_preview_only_after_success() -> None:
    repository = ImportSessionRepository()
    importer = AsyncMock()
    importer.import_text.return_value = AIRecipeImport(
        recipe=_recipe("AI soup"),
        extracted_fields=["title", "ingredients", "instructions"],
        estimated_fields=[],
        warnings=[],
    )
    orchestrator = _orchestrator(importer=importer, repository=repository)
    normal_result = ImportResult(status=ImportStatus.SUCCESS, recipe=_recipe())
    orchestrator.register_normal_result(
        result=normal_result,
        source=ImportSource(
            source_type=SourceType.MANUAL,
            raw_text="Original source",
        ),
    )

    session = asyncio.run(
        orchestrator.parse_with_ai(
            normal_result.import_id,
            reason=AIParseReason.USER_REQUESTED_REPARSE,
        )
    )

    assert session.active_result.recipe.title == "AI soup"
    assert session.previous_results[-1].recipe.title == "Normal soup"
    assert session.metadata.parse_method is ParseMethod.AI_REPARSE
    assert session.metadata.attempts[-1].success is True


def test_failed_ai_reparse_preserves_normal_candidate() -> None:
    repository = ImportSessionRepository()
    importer = AsyncMock()
    importer.import_text.side_effect = AIUnavailableError("offline")
    orchestrator = _orchestrator(importer=importer, repository=repository)
    normal_result = ImportResult(status=ImportStatus.SUCCESS, recipe=_recipe())
    orchestrator.register_normal_result(
        result=normal_result,
        source=ImportSource(
            source_type=SourceType.MANUAL,
            raw_text="Original source",
        ),
    )

    with pytest.raises(AIUnavailableError):
        asyncio.run(
            orchestrator.parse_with_ai(
                normal_result.import_id,
                reason=AIParseReason.USER_REQUESTED_REPARSE,
            )
        )

    session = repository.get(normal_result.import_id)

    assert session.active_result.recipe.title == "Normal soup"
    assert session.status is ImportProcessingStatus.AI_PARSE_FAILED
    assert session.metadata.attempts[-1].success is False


def test_failed_normal_parse_can_be_retried_with_same_source() -> None:
    repository = ImportSessionRepository()
    importer = AsyncMock()
    importer.import_text.return_value = AIRecipeImport(
        recipe=_recipe("Recovered soup"),
        extracted_fields=["title", "ingredients", "instructions"],
        estimated_fields=[],
        warnings=[],
    )
    orchestrator = _orchestrator(importer=importer, repository=repository)
    failed = ImportResult(
        status=ImportStatus.FAILED,
        raw_input_reference="Original source",
    )
    orchestrator.register_normal_result(
        result=failed,
        source=ImportSource(
            source_type=SourceType.MANUAL,
            raw_text="Original source",
        ),
    )

    session = asyncio.run(
        orchestrator.parse_with_ai(
            failed.import_id,
            reason=AIParseReason.NORMAL_PARSE_FAILED,
        )
    )

    assert session.active_result.recipe.title == "Recovered soup"
    assert session.previous_results[-1].status is ImportStatus.FAILED


def test_ai_parse_offers_metadata_enrichment_without_running_it_automatically() -> None:
    repository = ImportSessionRepository()
    importer = AsyncMock()
    incomplete = _recipe("AI soup").model_copy(
        update={
            "servings": None,
            "tags": [],
        }
    )
    importer.import_text.return_value = AIRecipeImport(
        recipe=incomplete,
        extracted_fields=["title", "ingredients", "instructions"],
        estimated_fields=[],
        warnings=[],
    )
    enrichment = AsyncMock()
    loader = AsyncMock()
    loader.load_text.return_value = "Original source"
    orchestrator = AIImportOrchestrator(
        repository=repository,
        importer=importer,
        enrichment_service=enrichment,
        source_loader=loader,
        ai_model="qwen3.5:4b",
        enrich_missing_fields=True,
    )
    normal_result = ImportResult(status=ImportStatus.SUCCESS, recipe=_recipe())
    orchestrator.register_normal_result(
        result=normal_result,
        source=ImportSource(
            source_type=SourceType.MANUAL,
            raw_text="Original source",
        ),
    )

    session = asyncio.run(
        orchestrator.parse_with_ai(
            normal_result.import_id,
            reason=AIParseReason.USER_REQUESTED_REPARSE,
        )
    )

    enrichment.enrich.assert_not_awaited()
    assert session.active_result.recipe.servings is None
    assert session.active_result.recipe.tags == []
    assert session.metadata.enrichable_fields == ["servings", "tags"]


def test_manual_enrichment_failure_preserves_current_preview() -> None:
    repository = ImportSessionRepository()
    importer = AsyncMock()
    enrichment = AsyncMock()
    enrichment.enrich.side_effect = AIUnavailableError("offline")
    loader = AsyncMock()
    loader.load_text.return_value = "Original source"
    orchestrator = AIImportOrchestrator(
        repository=repository,
        importer=importer,
        enrichment_service=enrichment,
        source_loader=loader,
        ai_model="qwen3.5:4b",
        enrich_missing_fields=True,
    )
    incomplete = _recipe().model_copy(
        update={
            "servings": None,
            "tags": [],
        }
    )
    normal_result = ImportResult(
        status=ImportStatus.SUCCESS,
        recipe=incomplete,
    )
    orchestrator.register_normal_result(
        result=normal_result,
        source=ImportSource(
            source_type=SourceType.MANUAL,
            raw_text="Original source",
        ),
    )

    with pytest.raises(AIUnavailableError):
        asyncio.run(orchestrator.enrich_missing_metadata(normal_result.import_id))

    session = repository.get(normal_result.import_id)
    assert session.active_result.recipe.title == "Normal soup"
    assert session.active_result.recipe.servings is None
    assert session.active_result.warnings == []
    assert session.status is ImportProcessingStatus.AWAITING_CONFIRMATION
    assert session.metadata.attempts[-1].success is False


def test_normal_enrichment_only_publishes_successful_merge() -> None:
    repository = ImportSessionRepository()
    importer = AsyncMock()
    enrichment = AsyncMock()
    incomplete = _recipe().model_copy(update={"servings": None})
    enriched = incomplete.model_copy(update={"servings": 6})
    enrichment.enrich.return_value = EnrichmentResult(
        recipe=enriched,
        extracted_fields=[],
        estimated_fields=["servings"],
        warnings=[],
    )
    loader = AsyncMock()
    loader.load_text.return_value = "Original source"
    orchestrator = AIImportOrchestrator(
        repository=repository,
        importer=importer,
        enrichment_service=enrichment,
        source_loader=loader,
        ai_model="qwen3.5:4b",
        enrich_missing_fields=True,
    )
    normal_result = ImportResult(
        status=ImportStatus.SUCCESS,
        recipe=incomplete,
    )
    orchestrator.register_normal_result(
        result=normal_result,
        source=ImportSource(
            source_type=SourceType.MANUAL,
            raw_text="Original source",
        ),
    )

    session = asyncio.run(orchestrator.enrich_missing_metadata(normal_result.import_id))

    assert session.active_result.recipe.servings == 6
    assert session.previous_results[-1].recipe.servings is None
    assert session.metadata.estimated_fields == ["servings"]
    assert session.metadata.parse_method is ParseMethod.AI_ENRICHMENT
    assert session.metadata.enrichable_fields == []
    assert session.metadata.attempts[-1].success is True
