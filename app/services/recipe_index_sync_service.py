from pathlib import Path

import yaml
from app.database.models.recipe import RecipeRecord
from app.database.repositories.recipe_repository import (
    RecipeRepository,
)
from app.utils.recipe_metadata import normalize_meal_types, normalize_tags
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

        tags = self._string_list(metadata.get("tags"))
        meal_types = normalize_meal_types(
            self._string_list(metadata.get("meal_types"))
        ) or ["dinner"]
        preparation_time_value = metadata.get("preparation_time_minutes")
        if preparation_time_value is None:
            preparation_time_value = metadata.get("total_time_minutes")
        preparation_time = self._optional_int(preparation_time_value)
        default_servings = self._optional_int(metadata.get("servings")) or 2
        difficulty_value = metadata.get("difficulty")
        difficulty = (
            str(difficulty_value).strip().casefold() if difficulty_value else "unknown"
        )
        vegetarian = self._optional_bool(metadata.get("vegetarian"))
        vegan = self._optional_bool(metadata.get("vegan"))
        suitable_for_leftovers = (
            self._optional_bool(metadata.get("suitable_for_leftovers")) or False
        )
        leftover_servings = self._optional_int(metadata.get("leftover_servings"))
        leftover_days = self._optional_int(metadata.get("leftover_days")) or 1

        existing = self.repository.get_by_identifier(identifier)

        if existing is None:
            self.repository.add(
                RecipeRecord(
                    identifier=identifier,
                    title=title,
                    file_path=str(recipe_path),
                    source_url=source_url,
                    content_hash=content_hash,
                    tags=normalize_tags(tags),
                    meal_types=meal_types,
                    preparation_time_minutes=preparation_time,
                    difficulty=difficulty,
                    default_servings=default_servings,
                    vegetarian=vegetarian,
                    vegan=vegan,
                    suitable_for_leftovers=suitable_for_leftovers,
                    leftover_servings=leftover_servings,
                    leftover_days=leftover_days,
                )
            )
            return

        self.repository.update(
            existing,
            title=title,
            file_path=str(recipe_path),
            source_url=source_url,
            content_hash=content_hash,
            tags=normalize_tags(tags),
            meal_types=meal_types,
            preparation_time_minutes=preparation_time,
            difficulty=difficulty,
            default_servings=default_servings,
            vegetarian=vegetarian,
            vegan=vegan,
            suitable_for_leftovers=suitable_for_leftovers,
            leftover_servings=leftover_servings,
            leftover_days=leftover_days,
        )

    @staticmethod
    def _string_list(value: object) -> list[str]:
        if isinstance(value, str):
            return [value]
        if isinstance(value, list):
            return [item for item in value if isinstance(item, str)]
        return []

    @staticmethod
    def _optional_int(value: object) -> int | None:
        if isinstance(value, bool):
            return None
        if not isinstance(value, int | float | str):
            return None
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return None
        return parsed if parsed >= 0 else None

    @staticmethod
    def _optional_bool(value: object) -> bool | None:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            normalized = value.strip().casefold()
            if normalized in {"true", "yes", "ja", "1"}:
                return True
            if normalized in {"false", "no", "nee", "0"}:
                return False
        return None

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

    def sync_file(
        self,
        recipe_path: Path,
    ) -> None:
        if not recipe_path.is_file():
            raise FileNotFoundError(f"Recipe file does not exist: {recipe_path}")

        self._sync_file(recipe_path)
        self.session.commit()

    def remove_by_identifier(
        self,
        identifier: str,
    ) -> bool:
        deleted = self.repository.delete_by_identifier(identifier)

        if deleted:
            self.session.commit()

        return deleted
