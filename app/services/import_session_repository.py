import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from threading import RLock
from uuid import UUID

from app.models.import_result import ImportResult, ImportStatus
from app.models.import_session import (
    ImportProcessingStatus,
    ImportSession,
    ImportSource,
    RecipeImportMetadata,
)


class ImportSessionError(RuntimeError):
    pass


class ImportSessionNotFoundError(ImportSessionError):
    pass


class ImportAlreadyProcessingError(ImportSessionError):
    pass


class ImportPermissionError(ImportSessionError):
    pass


class ImportSessionClosedError(ImportSessionError):
    pass


class ImportSessionRepository:
    def __init__(self) -> None:
        self._sessions: dict[UUID, ImportSession] = {}
        self._processing_locks: dict[UUID, asyncio.Lock] = {}
        self._guard = RLock()

    def register(
        self,
        *,
        result: ImportResult,
        source: ImportSource,
        discord_user_id: int | None = None,
        metadata: RecipeImportMetadata | None = None,
    ) -> ImportSession:
        processing_status = (
            ImportProcessingStatus.NORMAL_PARSE_FAILED
            if result.status is ImportStatus.FAILED
            else ImportProcessingStatus.AWAITING_CONFIRMATION
        )
        session = ImportSession(
            import_id=result.import_id,
            created_at=result.created_at,
            discord_user_id=discord_user_id,
            source=source,
            status=processing_status,
            active_result=result,
            metadata=metadata
            or RecipeImportMetadata(
                parser_name=result.extractor,
                normal_parser_error=self._normal_error(result),
            ),
        )

        with self._guard:
            self._sessions[result.import_id] = session
            self._processing_locks.setdefault(result.import_id, asyncio.Lock())

        return session.model_copy(deep=True)

    def get(self, import_id: UUID) -> ImportSession:
        with self._guard:
            try:
                session = self._sessions[import_id]
            except KeyError as exc:
                raise ImportSessionNotFoundError(
                    f"Import {import_id} was not found"
                ) from exc

        return session.model_copy(deep=True)

    def update(self, session: ImportSession) -> ImportSession:
        with self._guard:
            if session.import_id not in self._sessions:
                raise ImportSessionNotFoundError(
                    f"Import {session.import_id} was not found"
                )
            self._sessions[session.import_id] = session.model_copy(deep=True)

        return session.model_copy(deep=True)

    def set_owner(self, import_id: UUID, discord_user_id: int | None) -> ImportSession:
        session = self.get(import_id)

        if discord_user_id is None:
            return session

        if (
            session.discord_user_id is not None
            and session.discord_user_id != discord_user_id
        ):
            raise ImportPermissionError(
                "Only the user who started this import may continue it"
            )

        if session.discord_user_id is None:
            session.discord_user_id = discord_user_id
            return self.update(session)

        return session

    def mark_saved(self, import_id: UUID) -> ImportSession:
        session = self.get(import_id)
        session.status = ImportProcessingStatus.SAVED
        self._remove_temporary_file(session)
        session.source.temporary_file_path = None
        return self.update(session)

    def cancel(self, import_id: UUID) -> ImportSession:
        session = self.get(import_id)
        session.status = ImportProcessingStatus.CANCELLED
        self._remove_temporary_file(session)
        session.source.temporary_file_path = None
        return self.update(session)

    @asynccontextmanager
    async def processing(self, import_id: UUID) -> AsyncIterator[None]:
        session = self.get(import_id)

        if session.status in {
            ImportProcessingStatus.SAVED,
            ImportProcessingStatus.CANCELLED,
        }:
            raise ImportSessionClosedError(
                f"Import {import_id} is already {session.status.value}"
            )

        with self._guard:
            lock = self._processing_locks.setdefault(import_id, asyncio.Lock())

        if lock.locked():
            raise ImportAlreadyProcessingError(
                "This import is already being processed with AI"
            )

        await lock.acquire()

        try:
            yield
        finally:
            lock.release()

    @staticmethod
    def _normal_error(result: ImportResult) -> str | None:
        if result.status is not ImportStatus.FAILED or not result.warnings:
            return None
        return result.warnings[0].message

    @staticmethod
    def _remove_temporary_file(session: ImportSession) -> None:
        path = session.source.temporary_file_path

        if path is not None:
            path.unlink(missing_ok=True)
