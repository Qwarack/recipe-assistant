from pathlib import Path

import pytest
from app.models.recipe import Ingredient, Recipe, SourceType
from app.services.recipe_storage import (
    RecipeAlreadyExistsError,
    RecipeStorage,
)


class FakeRenderer:
    def render(self, recipe: Recipe) -> str:
        return f"# {recipe.title}\n"


def make_recipe() -> Recipe:
    return Recipe(
        title="Pasta Carbonara",
        source_type=SourceType.MANUAL,
        ingredients=[
            Ingredient(name="pasta"),
        ],
        instructions=[
            "Cook the pasta.",
        ],
    )


def test_storage_saves_recipe_as_markdown(
    tmp_path: Path,
) -> None:
    storage = RecipeStorage(
        recipes_path=tmp_path,
        renderer=FakeRenderer(),
    )

    destination = storage.save(make_recipe())

    assert destination == tmp_path / "pasta-carbonara.md"
    assert destination.read_text(encoding="utf-8") == ("# Pasta Carbonara\n")


def test_storage_does_not_overwrite_existing_recipe(
    tmp_path: Path,
) -> None:
    storage = RecipeStorage(
        recipes_path=tmp_path,
        renderer=FakeRenderer(),
    )

    storage.save(make_recipe())

    with pytest.raises(RecipeAlreadyExistsError):
        storage.save(make_recipe())
