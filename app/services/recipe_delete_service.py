from pathlib import Path


class RecipeDeleteService:
    def __init__(self, recipes_path: Path) -> None:
        self.recipes_path = recipes_path

    def delete_by_identifier(
        self,
        identifier: str,
    ) -> bool:
        safe_identifier = Path(identifier).name
        recipe_path = self.recipes_path / f"{safe_identifier}.md"

        if not recipe_path.is_file():
            return False

        recipe_path.unlink()
        return True
