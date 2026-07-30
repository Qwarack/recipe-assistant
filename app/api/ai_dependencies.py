from collections.abc import Generator
from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.ai.client import OllamaClient
from app.core.config import get_settings
from app.core.http_client import SafeHttpClient
from app.importers.ai_recipe import AIRecipeImporter
from app.services.ai_import_orchestrator import (
    AIImportOrchestrator,
    SourceContextLoader,
)
from app.services.import_session_repository import ImportSessionRepository
from app.services.recipe_enrichment_service import RecipeEnrichmentService


@lru_cache
def get_import_session_repository() -> ImportSessionRepository:
    return ImportSessionRepository()


def build_ai_import_orchestrator(
    http_client: SafeHttpClient,
) -> AIImportOrchestrator:
    settings = get_settings()
    client = OllamaClient(
        base_url=settings.ollama_base_url,
        model=settings.ollama_model,
        timeout_seconds=settings.ollama_timeout_seconds,
        max_retries=settings.ollama_max_retries,
        max_prompt_characters=settings.max_ai_prompt_characters,
    )
    repository = get_import_session_repository()

    return AIImportOrchestrator(
        repository=repository,
        importer=AIRecipeImporter(
            client=client,
            max_source_characters=settings.max_ai_source_characters,
        ),
        enrichment_service=RecipeEnrichmentService(
            client=client,
            max_source_characters=settings.max_ai_source_characters,
        ),
        source_loader=SourceContextLoader(
            http_client=http_client,
            max_source_characters=settings.max_ai_source_characters,
        ),
        ai_model=settings.ollama_model,
        enrich_missing_fields=settings.ai_enrich_missing_fields,
    )


def get_ai_http_client() -> Generator[SafeHttpClient, None, None]:
    with SafeHttpClient() as client:
        yield client


def create_ai_import_orchestrator(
    http_client: Annotated[
        SafeHttpClient,
        Depends(get_ai_http_client),
    ],
) -> AIImportOrchestrator:
    return build_ai_import_orchestrator(http_client)
