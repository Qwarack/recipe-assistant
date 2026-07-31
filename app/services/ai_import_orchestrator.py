import asyncio
import logging
from datetime import UTC, datetime
from pathlib import Path
from time import monotonic
from uuid import UUID

from app.ai.exceptions import (
    AIAuthenticationError,
    AIFallbackNotAllowedError,
    AIServiceError,
)
from app.core.http_client import HttpFetchError, SafeHttpClient
from app.importers.ai_recipe import (
    AIRecipeContext,
    AIRecipeImport,
    AIRecipeImporter,
)
from app.models.import_result import (
    ImportResult,
    ImportStatus,
    ImportWarning,
)
from app.models.import_session import (
    AIParseReason,
    ConfidenceAction,
    ImportProcessingStatus,
    ImportSession,
    ImportSource,
    ParseAttempt,
    ParseMethod,
)
from app.models.recipe import SourceType
from app.services.import_confidence import ConfidencePolicy
from app.services.import_session_repository import ImportSessionRepository
from app.services.recipe_enrichment_service import (
    RecipeEnrichmentService,
    detect_missing_fields,
)
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

LOCAL_PARSE_METHODS = {
    ParseMethod.AI_TEXT,
    ParseMethod.AI_IMAGE,
    ParseMethod.AI_REPARSE,
}


class AIImportSourceError(AIServiceError):
    pass


class SourceContextLoader:
    def __init__(
        self,
        *,
        http_client: SafeHttpClient,
        max_source_characters: int,
    ) -> None:
        self.http_client = http_client
        self.max_source_characters = max_source_characters

    async def load_text(self, source: ImportSource) -> str:
        if source.raw_text is not None:
            return source.raw_text[: self.max_source_characters]

        if source.source_url is not None:
            try:
                html = await asyncio.to_thread(
                    self.http_client.get_text,
                    source.source_url,
                )
            except HttpFetchError as exc:
                raise AIImportSourceError(
                    "The original web page could not be loaded for AI parsing"
                ) from exc

            return self._visible_text(html)

        raise AIImportSourceError("No textual source is available for AI parsing")

    def _visible_text(self, html: str) -> str:
        soup = BeautifulSoup(html, "html.parser")

        for element in soup(["script", "style", "noscript"]):
            element.decompose()

        return "\n".join(soup.stripped_strings)[: self.max_source_characters]

    @staticmethod
    def load_image(source: ImportSource) -> bytes:
        path = source.temporary_file_path

        if path is None:
            raise AIImportSourceError("The original image is no longer available")

        try:
            image = Path(path).read_bytes()
        except OSError as exc:
            raise AIImportSourceError("The original image could not be loaded") from exc

        if not image:
            raise AIImportSourceError("The original image is empty")

        return image


class AIImportOrchestrator:
    def __init__(
        self,
        *,
        repository: ImportSessionRepository,
        importer: AIRecipeImporter,
        enrichment_service: RecipeEnrichmentService,
        source_loader: SourceContextLoader,
        ai_model: str,
        enrich_missing_fields: bool = True,
        openai_importer: AIRecipeImporter | None = None,
        openai_model: str | None = None,
        confidence_policy: ConfidencePolicy | None = None,
    ) -> None:
        self.repository = repository
        self.importer = importer
        self.enrichment_service = enrichment_service
        self.source_loader = source_loader
        self.ai_model = ai_model
        self.enrich_missing_fields = enrich_missing_fields
        self.openai_importer = openai_importer
        self.openai_model = openai_model
        self.confidence_policy = confidence_policy or ConfidencePolicy()

    def register_normal_result(
        self,
        *,
        result: ImportResult,
        source: ImportSource,
        discord_user_id: int | None = None,
    ) -> ImportSession:
        session = self.repository.register(
            result=result,
            source=source,
            discord_user_id=discord_user_id,
        )

        if result.recipe is not None:
            self._update_missing_fields(session)
        self._update_confidence(session, method=ParseMethod.NORMAL)
        session = self.repository.update(session)

        return session

    async def enrich_missing_metadata(
        self,
        import_id: UUID,
        *,
        discord_user_id: int | None = None,
    ) -> ImportSession:
        started_at = monotonic()
        self.repository.set_owner(import_id, discord_user_id)

        async with self.repository.processing(import_id):
            session = self.repository.get(import_id)
            recipe = session.active_result.recipe

            if recipe is None:
                raise AIImportSourceError(
                    "Deze import bevat geen receptmetadata om aan te vullen."
                )

            report = detect_missing_fields(recipe)
            if not self.enrich_missing_fields or not report.enrichable:
                self._update_missing_fields(session)
                return self.repository.update(session)

            attempt = ParseAttempt(
                attempt_number=len(session.metadata.attempts) + 1,
                method=ParseMethod.AI_ENRICHMENT,
                model=self.ai_model,
            )
            session.status = ImportProcessingStatus.PROCESSING_AI
            session.metadata.attempts.append(attempt)
            self.repository.update(session)

            try:
                source_text = (
                    ""
                    if session.source.source_type is SourceType.IMAGE
                    else await self.source_loader.load_text(session.source)
                )
                enrichment = await self.enrichment_service.enrich(
                    recipe=recipe,
                    source_context=source_text,
                    report=report,
                )
            except AIServiceError as exc:
                session = self.repository.get(import_id)
                failed_attempt = session.metadata.attempts[-1]
                failed_attempt.finished_at = datetime.now(UTC)
                failed_attempt.error_code = type(exc).__name__
                failed_attempt.success = False
                session.status = ImportProcessingStatus.AWAITING_CONFIRMATION
                self.repository.update(session)
                self._log_attempt(
                    session,
                    method=ParseMethod.AI_ENRICHMENT,
                    started_at=started_at,
                    success=False,
                    error_code=type(exc).__name__,
                )
                raise

            session = self.repository.get(import_id)
            session.previous_results.append(session.active_result)
            warnings = [
                *session.active_result.warnings,
                *(
                    ImportWarning(code="ai_enrichment_warning", message=message)
                    for message in enrichment.warnings
                ),
            ]
            session.active_result = session.active_result.model_copy(
                update={
                    "recipe": enrichment.recipe,
                    "status": (
                        ImportStatus.PARTIAL
                        if warnings
                        else session.active_result.status
                    ),
                    "warnings": warnings,
                }
            )
            session.status = ImportProcessingStatus.AWAITING_CONFIRMATION
            session.metadata.parse_method = ParseMethod.AI_ENRICHMENT
            session.metadata.ai_model = self.ai_model
            session.metadata.extracted_fields = list(
                dict.fromkeys(
                    [
                        *session.metadata.extracted_fields,
                        *enrichment.extracted_fields,
                    ]
                )
            )
            session.metadata.estimated_fields = list(
                dict.fromkeys(
                    [
                        *session.metadata.estimated_fields,
                        *enrichment.estimated_fields,
                    ]
                )
            )
            successful_attempt = session.metadata.attempts[-1]
            successful_attempt.finished_at = datetime.now(UTC)
            successful_attempt.success = True
            successful_attempt.warnings = enrichment.warnings
            self._update_missing_fields(session)
            self._update_confidence(
                session,
                method=ParseMethod.AI_REPARSE,
                estimated_fields=session.metadata.estimated_fields,
            )
            updated = self.repository.update(session)
            self._log_attempt(
                updated,
                method=ParseMethod.AI_ENRICHMENT,
                started_at=started_at,
                success=True,
            )
            return updated

    async def parse_with_ai(
        self,
        import_id: UUID,
        *,
        reason: AIParseReason,
        discord_user_id: int | None = None,
    ) -> ImportSession:
        started_at = monotonic()
        self.repository.set_owner(import_id, discord_user_id)

        async with self.repository.processing(import_id):
            session = self.repository.get(import_id)
            method = self._method_for_reason(reason)
            attempt = ParseAttempt(
                attempt_number=len(session.metadata.attempts) + 1,
                method=method,
                model=self.ai_model,
            )
            session.status = ImportProcessingStatus.PROCESSING_AI
            session.metadata.attempts.append(attempt)
            self.repository.update(session)

            try:
                imported = await self._parse_source(session, reason=reason)
            except AIServiceError as exc:
                session = self.repository.get(import_id)
                failed_attempt = session.metadata.attempts[-1]
                failed_attempt.finished_at = datetime.now(UTC)
                failed_attempt.error_code = type(exc).__name__
                failed_attempt.success = False
                session.status = ImportProcessingStatus.AI_PARSE_FAILED
                self.repository.update(session)
                self._log_attempt(
                    session,
                    method=method,
                    started_at=started_at,
                    success=False,
                    error_code=type(exc).__name__,
                )
                raise

            session = self.repository.get(import_id)
            previous_result = session.active_result
            warnings = [
                ImportWarning(code="ai_parse_warning", message=message)
                for message in imported.warnings
            ]
            result = ImportResult(
                import_id=import_id,
                created_at=session.created_at,
                status=ImportStatus.PARTIAL if warnings else ImportStatus.SUCCESS,
                recipe=imported.recipe,
                warnings=warnings,
                extractor=imported.recipe.extractor,
                raw_input_reference=previous_result.raw_input_reference,
            )
            session.previous_results.append(previous_result)
            session.active_result = result
            session.status = ImportProcessingStatus.AWAITING_CONFIRMATION
            session.metadata.parse_method = method
            session.metadata.parser_name = imported.recipe.extractor
            session.metadata.ai_model = self.ai_model
            session.metadata.extracted_fields = imported.extracted_fields
            session.metadata.estimated_fields = imported.estimated_fields
            session.metadata.warnings = imported.warnings
            successful_attempt = session.metadata.attempts[-1]
            successful_attempt.finished_at = datetime.now(UTC)
            successful_attempt.success = True
            successful_attempt.warnings = imported.warnings
            self._update_missing_fields(session)
            self._update_confidence(
                session,
                method=method,
                model_confidence=imported.confidence,
                model_reasons=imported.confidence_reasons,
                estimated_fields=imported.estimated_fields,
            )
            updated = self.repository.update(session)
            self._log_attempt(
                updated,
                method=method,
                started_at=started_at,
                success=True,
            )
            return updated

    async def parse_with_openai(
        self,
        import_id: UUID,
        *,
        discord_user_id: int | None = None,
    ) -> ImportSession:
        if self.openai_importer is None or self.openai_model is None:
            raise AIAuthenticationError("OpenAI fallback is not configured")

        started_at = monotonic()
        self.repository.set_owner(import_id, discord_user_id)

        async with self.repository.processing(import_id):
            session = self.repository.get(import_id)
            if not self.is_openai_fallback_allowed(session):
                raise AIFallbackNotAllowedError(
                    "OpenAI may only be used after a failed or low-confidence "
                    "local AI parse"
                )

            attempt = ParseAttempt(
                attempt_number=len(session.metadata.attempts) + 1,
                method=ParseMethod.OPENAI_FALLBACK,
                model=self.openai_model,
            )
            session.status = ImportProcessingStatus.PROCESSING_AI
            session.metadata.attempts.append(attempt)
            self.repository.update(session)

            try:
                imported = await self._parse_original_source_with(
                    session,
                    importer=self.openai_importer,
                )
            except AIServiceError as exc:
                session = self.repository.get(import_id)
                failed_attempt = session.metadata.attempts[-1]
                failed_attempt.finished_at = datetime.now(UTC)
                failed_attempt.error_code = type(exc).__name__
                failed_attempt.success = False
                session.status = ImportProcessingStatus.OPENAI_PARSE_FAILED
                self.repository.update(session)
                self._log_attempt(
                    session,
                    method=ParseMethod.OPENAI_FALLBACK,
                    started_at=started_at,
                    success=False,
                    error_code=type(exc).__name__,
                )
                raise

            session = self.repository.get(import_id)
            previous_result = session.active_result
            warnings = [
                ImportWarning(code="ai_parse_warning", message=message)
                for message in imported.warnings
            ]
            session.previous_results.append(previous_result)
            session.active_result = ImportResult(
                import_id=import_id,
                created_at=session.created_at,
                status=ImportStatus.PARTIAL if warnings else ImportStatus.SUCCESS,
                recipe=imported.recipe,
                warnings=warnings,
                extractor=imported.recipe.extractor,
                raw_input_reference=previous_result.raw_input_reference,
            )
            session.status = ImportProcessingStatus.AWAITING_CONFIRMATION
            session.metadata.parse_method = ParseMethod.OPENAI_FALLBACK
            session.metadata.parser_name = imported.recipe.extractor
            session.metadata.ai_model = self.openai_model
            session.metadata.extracted_fields = imported.extracted_fields
            session.metadata.estimated_fields = imported.estimated_fields
            session.metadata.warnings = imported.warnings
            successful_attempt = session.metadata.attempts[-1]
            successful_attempt.finished_at = datetime.now(UTC)
            successful_attempt.success = True
            successful_attempt.warnings = imported.warnings
            self._update_missing_fields(session)
            self._update_confidence(
                session,
                method=ParseMethod.OPENAI_FALLBACK,
                model_confidence=imported.confidence,
                model_reasons=imported.confidence_reasons,
                estimated_fields=imported.estimated_fields,
            )
            updated = self.repository.update(session)
            self._log_attempt(
                updated,
                method=ParseMethod.OPENAI_FALLBACK,
                started_at=started_at,
                success=True,
            )
            return updated

    @staticmethod
    def is_openai_fallback_allowed(session: ImportSession) -> bool:
        if session.metadata.confidence_action is ConfidenceAction.OFFER_OPENAI:
            return True
        if not session.metadata.attempts:
            return False

        latest_attempt = session.metadata.attempts[-1]
        return (
            latest_attempt.method in LOCAL_PARSE_METHODS and not latest_attempt.success
        ) or (
            latest_attempt.method is ParseMethod.OPENAI_FALLBACK
            and not latest_attempt.success
        )

    async def _parse_source(
        self,
        session: ImportSession,
        *,
        reason: AIParseReason,
    ) -> AIRecipeImport:
        context = AIRecipeContext(
            source_type=session.source.source_type,
            source_url=session.source.source_url,
            source_name=session.source.original_filename,
        )

        if (
            reason is AIParseReason.IMAGE_INPUT
            or session.source.source_type is SourceType.IMAGE
        ):
            return await self.importer.import_image(
                self.source_loader.load_image(session.source),
                context=context,
            )

        source_text = await self.source_loader.load_text(session.source)
        return await self.importer.import_text(source_text, context=context)

    async def _parse_original_source_with(
        self,
        session: ImportSession,
        *,
        importer: AIRecipeImporter,
    ) -> AIRecipeImport:
        context = AIRecipeContext(
            source_type=session.source.source_type,
            source_url=session.source.source_url,
            source_name=session.source.original_filename,
        )
        if session.source.source_type is SourceType.IMAGE:
            return await importer.import_image(
                self.source_loader.load_image(session.source),
                context=context,
            )

        source_text = await self.source_loader.load_text(session.source)
        return await importer.import_text(source_text, context=context)

    @staticmethod
    def _method_for_reason(reason: AIParseReason) -> ParseMethod:
        if reason is AIParseReason.IMAGE_INPUT:
            return ParseMethod.AI_IMAGE
        if reason is AIParseReason.USER_REQUESTED_REPARSE:
            return ParseMethod.AI_REPARSE
        return ParseMethod.AI_TEXT

    def _update_missing_fields(self, session: ImportSession) -> None:
        recipe = session.active_result.recipe
        if recipe is None:
            session.metadata.missing_fields = []
            session.metadata.enrichable_fields = []
            session.metadata.unsafe_to_guess_fields = []
            return

        report = detect_missing_fields(recipe)
        session.metadata.missing_fields = [
            *report.required,
            *report.enrichable,
            *report.unsafe_to_guess,
        ]
        session.metadata.enrichable_fields = (
            report.enrichable if self.enrich_missing_fields else []
        )
        session.metadata.unsafe_to_guess_fields = report.unsafe_to_guess

    def _update_confidence(
        self,
        session: ImportSession,
        *,
        method: ParseMethod,
        model_confidence: float | None = None,
        model_reasons: list[str] | None = None,
        estimated_fields: list[str] | None = None,
    ) -> None:
        local_successful_attempts = sum(
            attempt.method in LOCAL_PARSE_METHODS and attempt.success
            for attempt in session.metadata.attempts
        )
        assessment = self.confidence_policy.assess(
            session.active_result,
            method=method,
            model_confidence=model_confidence,
            model_reasons=model_reasons,
            estimated_fields=estimated_fields,
            local_successful_attempts=local_successful_attempts,
        )
        session.metadata.confidence_action = assessment.action
        session.metadata.confidence_reasons = assessment.reasons

        result = session.active_result
        warnings = [
            warning
            for warning in result.warnings
            if warning.code != "confidence_review_recommended"
        ]
        if (
            result.recipe is not None
            and assessment.action is not ConfidenceAction.READY
        ):
            warnings.append(
                ImportWarning(
                    code="confidence_review_recommended",
                    message=self._confidence_warning(
                        assessment.score,
                        assessment.action,
                    ),
                )
            )

        status = result.status
        if result.recipe is not None:
            status = ImportStatus.PARTIAL if warnings else ImportStatus.SUCCESS
        session.active_result = result.model_copy(
            update={
                "confidence": assessment.score,
                "warnings": warnings,
                "status": status,
            }
        )

    @staticmethod
    def _confidence_warning(
        score: float,
        action: ConfidenceAction,
    ) -> str:
        percentage = round(score * 100)
        if action is ConfidenceAction.REVIEW_WARNING:
            advice = "Controleer de preview extra zorgvuldig voordat je opslaat."
        elif action is ConfidenceAction.TRY_LOCAL_AI:
            advice = "Laat Qwen3.5 het oorspronkelijke recept controleren."
        elif action is ConfidenceAction.RETRY_LOCAL_AI:
            advice = "Probeer Qwen3.5 nog één keer voor een betrouwbaarder resultaat."
        elif action is ConfidenceAction.OFFER_OPENAI:
            advice = (
                "Qwen3.5 blijft onzeker; ChatGPT is nu als laatste optie beschikbaar."
            )
        else:
            advice = "Handmatige controle is nodig voordat je dit resultaat opslaat."
        return f"Parse-confidence: {percentage}%. {advice}"

    def _log_attempt(
        self,
        session: ImportSession,
        *,
        method: ParseMethod,
        started_at: float,
        success: bool,
        error_code: str | None = None,
    ) -> None:
        logger.info(
            "Recipe AI parse attempt completed",
            extra={
                "import_id": str(session.import_id),
                "discord_user_id": session.discord_user_id,
                "source_type": session.source.source_type.value,
                "parse_method": method.value,
                "ai_model": (
                    self.openai_model
                    if method is ParseMethod.OPENAI_FALLBACK
                    else self.ai_model
                ),
                "attempt_number": len(session.metadata.attempts),
                "duration_ms": round((monotonic() - started_at) * 1000),
                "success": success,
                "error_code": error_code,
                "missing_fields_count": len(session.metadata.missing_fields),
                "estimated_fields_count": len(session.metadata.estimated_fields),
                "confidence": session.active_result.confidence,
                "confidence_action": (
                    session.metadata.confidence_action.value
                    if session.metadata.confidence_action is not None
                    else None
                ),
            },
        )
