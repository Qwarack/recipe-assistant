from pathlib import Path

from app.services.recipe_detail_service import (
    RecipeDetailService,
)


def test_get_recipe_by_identifier(
    tmp_path: Path,
) -> None:
    recipe_path = tmp_path / "pasta-carbonara.md"

    recipe_path.write_text(
        """---
title: Pasta Carbonara
servings: 4
prep_time_minutes: 10
cook_time_minutes: 20
total_time_minutes: 30
source_url: https://example.com/carbonara
tags:
  - pasta
  - italian
meal_types:
  - dinner
---

# Pasta Carbonara

## Ingrediënten

- 400 g spaghetti
- 4 eieren
- 100 g parmezaan

## Bereiding

1. Kook de spaghetti.
2. Meng de eieren en kaas.
3. Voeg alles samen.
""",
        encoding="utf-8",
    )

    service = RecipeDetailService(recipes_path=tmp_path)

    result = service.get_by_identifier("pasta-carbonara")

    assert result is not None
    assert result.identifier == "pasta-carbonara"
    assert result.title == "Pasta Carbonara"
    assert result.servings == 4
    assert result.total_time_minutes == 30
    assert result.ingredients == [
        "400 g spaghetti",
        "4 eieren",
        "100 g parmezaan",
    ]
    assert result.instructions == [
        "Kook de spaghetti.",
        "Meng de eieren en kaas.",
        "Voeg alles samen.",
    ]
    assert result.tags == [
        "pasta",
        "italian",
    ]
    assert result.meal_types == [
        "dinner",
    ]
    assert str(result.source_url) == ("https://example.com/carbonara")


def test_get_recipe_returns_none_when_missing(
    tmp_path: Path,
) -> None:
    service = RecipeDetailService(recipes_path=tmp_path)

    result = service.get_by_identifier("bestaat-niet")

    assert result is None


def test_get_recipe_does_not_escape_recipes_directory(
    tmp_path: Path,
) -> None:
    outside_file = tmp_path.parent / "secret.md"

    outside_file.write_text(
        """---
title: Secret
---

# Secret
""",
        encoding="utf-8",
    )

    service = RecipeDetailService(recipes_path=tmp_path)

    result = service.get_by_identifier("../secret")

    assert result is None
