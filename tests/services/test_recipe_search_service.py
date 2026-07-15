from pathlib import Path

from app.services.recipe_search_service import (
    RecipeSearchService,
)


def test_search_finds_recipe_by_title(
    tmp_path: Path,
) -> None:
    recipe_path = tmp_path / "pasta-carbonara.md"

    recipe_path.write_text(
        """---
title: Pasta Carbonara
tags:
  - pasta
meal_types:
  - dinner
source_url: https://example.com/carbonara
---

# Pasta Carbonara
""",
        encoding="utf-8",
    )

    service = RecipeSearchService(recipes_path=tmp_path)

    results = service.search("carbonara")

    assert len(results) == 1
    assert results[0].title == "Pasta Carbonara"
    assert results[0].path == str(recipe_path)
    assert str(results[0].source_url) == ("https://example.com/carbonara")


def test_search_finds_recipe_by_tag(
    tmp_path: Path,
) -> None:
    recipe_path = tmp_path / "tomato-soup.md"

    recipe_path.write_text(
        """---
title: Tomato Soup
tags:
  - vegetarian
  - soup
meal_types:
  - lunch
---

# Tomato Soup
""",
        encoding="utf-8",
    )

    service = RecipeSearchService(recipes_path=tmp_path)

    results = service.search("vegetarian")

    assert len(results) == 1
    assert results[0].title == "Tomato Soup"


def test_search_returns_empty_list_for_blank_query(
    tmp_path: Path,
) -> None:
    service = RecipeSearchService(recipes_path=tmp_path)

    results = service.search("   ")

    assert results == []
