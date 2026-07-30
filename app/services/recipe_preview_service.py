from collections.abc import Callable

from app.importers.base import RecipeImporter
from app.models.import_result import ImportResult
from app.models.import_session import ImportSession, ImportSource
from app.services.ai_import_orchestrator import AIImportOrchestrator


class RecipePreviewService:
    def __init__(
        self,
        importer: RecipeImporter[str],
        *,
        ai_orchestrator: AIImportOrchestrator | None = None,
        source_factory: Callable[[str], ImportSource] | None = None,
    ) -> None:
        self.importer = importer
        self.ai_orchestrator = ai_orchestrator
        self.source_factory = source_factory
        self.last_session: ImportSession | None = None

    def preview(
        self,
        source: str,
    ) -> ImportResult:
        return self.importer.import_recipe(source)

    async def preview_with_enrichment(
        self,
        source: str,
        *,
        discord_user_id: int | None = None,
    ) -> ImportResult:
        result = self.preview(source)

        if self.ai_orchestrator is None or self.source_factory is None:
            return result

        session = self.ai_orchestrator.register_normal_result(
            result=result,
            source=self.source_factory(source),
            discord_user_id=discord_user_id,
        )

        if result.recipe is not None:
            session = await self.ai_orchestrator.enrich_normal_result(result.import_id)

        self.last_session = session
        return session.active_result
