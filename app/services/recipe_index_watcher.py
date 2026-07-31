import asyncio
import logging
from collections.abc import Hashable
from pathlib import Path

from app.services.recipe_index_sync_service import RecipeIndexSyncService
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)

FileSnapshot = tuple[tuple[Hashable, ...], ...]


class RecipeIndexWatcher:
    def __init__(
        self,
        *,
        session_factory: sessionmaker[Session],
        recipes_path: Path,
        interval_seconds: float = 2.0,
    ) -> None:
        self.session_factory = session_factory
        self.recipes_path = recipes_path
        self.interval_seconds = interval_seconds
        self._observed_snapshot: FileSnapshot | None = None
        self._synced_snapshot: FileSnapshot | None = None

    async def run(self) -> None:
        logger.info(
            "Automatic recipe index synchronization started",
            extra={
                "recipes_path": str(self.recipes_path),
                "interval_seconds": self.interval_seconds,
            },
        )
        while True:
            try:
                synced = await asyncio.to_thread(self.sync_if_stable_change)
                if synced:
                    logger.info(
                        "Recipe index synchronized after vault change",
                        extra={"recipes_path": str(self.recipes_path)},
                    )
            except Exception:
                logger.exception("Automatic recipe index synchronization failed")
            await asyncio.sleep(self.interval_seconds)

    def sync_if_stable_change(self) -> bool:
        snapshot = self._snapshot()
        if snapshot != self._observed_snapshot:
            self._observed_snapshot = snapshot
            return False
        if snapshot == self._synced_snapshot:
            return False

        with self.session_factory() as session:
            RecipeIndexSyncService(
                session=session,
                recipes_path=self.recipes_path,
            ).sync_all()

        self._synced_snapshot = snapshot
        return True

    def _snapshot(self) -> FileSnapshot:
        if not self.recipes_path.is_dir():
            return ()

        entries: list[tuple[Hashable, ...]] = []
        for recipe_path in sorted(self.recipes_path.glob("*.md")):
            try:
                stat = recipe_path.stat()
            except FileNotFoundError:
                continue
            entries.append(
                (
                    recipe_path.name,
                    stat.st_mtime_ns,
                    stat.st_size,
                )
            )
        return tuple(entries)
