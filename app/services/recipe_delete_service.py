from pathlib import Path

from app.services.recipe_index_sync_service import (
    RecipeIndexSyncService,
)


class RecipeDeleteService:
    def __init__(
        self,
        recipes_path: Path,
        index_sync_service: RecipeIndexSyncService | None = None,
    ) -> None:
        self.recipes_path = recipes_path
        self.index_sync_service = index_sync_service

    def delete_by_identifier(
        self,
        identifier: str,
    ) -> bool:
        safe_identifier = Path(identifier).name
        recipe_path = self.recipes_path / f"{safe_identifier}.md"

        if not recipe_path.is_file():
            return False

        recipe_path.unlink()

        if self.index_sync_service is not None:
            self.index_sync_service.remove_by_identifier(safe_identifier)

        return True
