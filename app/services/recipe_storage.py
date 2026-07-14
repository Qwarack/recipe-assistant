from pathlib import Path
from tempfile import NamedTemporaryFile

from app.models.recipe import Recipe
from app.services.markdown_renderer import RecipeMarkdownRenderer
from slugify import slugify


class RecipeAlreadyExistsError(FileExistsError):
    pass


class RecipeStorage:
    def __init__(
        self,
        recipes_path: Path,
        renderer: RecipeMarkdownRenderer,
    ) -> None:
        self.recipes_path = recipes_path
        self.renderer = renderer

    def save(self, recipe: Recipe) -> Path:
        self.recipes_path.mkdir(
            parents=True,
            exist_ok=True,
        )

        short_id = str(recipe.id).split("-")[0]
        filename = f"{slugify(recipe.title)}-{short_id}.md"
        destination = self.recipes_path / filename

        if destination.exists():
            raise RecipeAlreadyExistsError(
                f"Recipe file already exists: {destination.name}"
            )

        content = self.renderer.render(recipe)
        self._write_atomically(destination, content)

        return destination

    @staticmethod
    def _write_atomically(
        destination: Path,
        content: str,
    ) -> None:
        with NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=destination.parent,
            delete=False,
        ) as temporary_file:
            temporary_file.write(content)
            temporary_path = Path(temporary_file.name)

        temporary_path.replace(destination)
