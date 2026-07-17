from pathlib import Path

import yaml
from app.database.models.recipe import RecipeRecord
from app.database.repositories.recipe_repository import (
    RecipeRepository,
)
from sqlalchemy.orm import Session


class RecipeIndexSyncService:
    def __init__(
        self,
        *,
        session: Session,
        recipes_path: Path,
    ) -> None:
        self.session = session
        self.recipes_path = recipes_path
        self.repository = RecipeRepository(session)

    def sync_all(self) -> int:
        synced_count = 0

        for recipe_path in self.recipes_path.glob("*.md"):
            self._sync_file(recipe_path)
            synced_count += 1

        self.session.commit()

        return synced_count

    def _sync_file(
        self,
        recipe_path: Path,
    ) -> None:
        metadata = self._read_frontmatter(recipe_path)

        identifier = recipe_path.stem
        title = str(metadata.get("title") or identifier)

        source_url_value = metadata.get("source_url")
        source_url = str(source_url_value) if source_url_value else None

        content_hash_value = metadata.get("content_hash")
        content_hash = str(content_hash_value) if content_hash_value else None

        existing = self.repository.get_by_identifier(identifier)

        if existing is None:
            self.repository.add(
                RecipeRecord(
                    identifier=identifier,
                    title=title,
                    file_path=str(recipe_path),
                    source_url=source_url,
                    content_hash=content_hash,
                )
            )
            return

        self.repository.update(
            existing,
            title=title,
            file_path=str(recipe_path),
            source_url=source_url,
            content_hash=content_hash,
        )

    def _read_frontmatter(
        self,
        recipe_path: Path,
    ) -> dict[str, object]:
        text = recipe_path.read_text(encoding="utf-8")

        if not text.startswith("---"):
            return {}

        parts = text.split("---", maxsplit=2)

        if len(parts) < 3:
            return {}

        metadata = yaml.safe_load(parts[1])

        if not isinstance(metadata, dict):
            return {}

        return metadata
