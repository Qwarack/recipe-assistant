import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock

from app.bot.api_client import RecipeSearchResult
from app.bot.cogs.week import (
    WeekCommands,
    get_planning_start_date,
)


def test_planning_start_date_on_wednesday() -> None:
    result = get_planning_start_date(date(2026, 7, 15))

    assert result == date(2026, 7, 15)


def test_planning_start_date_on_saturday() -> None:
    result = get_planning_start_date(date(2026, 7, 18))

    assert result == date(2026, 7, 15)


def test_planning_start_date_on_monday() -> None:
    result = get_planning_start_date(date(2026, 7, 20))

    assert result == date(2026, 7, 15)


def test_recipe_autocomplete_returns_at_most_25_choices() -> None:
    api_client = MagicMock()
    api_client.search_recipes = AsyncMock(
        return_value=[
            RecipeSearchResult(
                identifier=f"pasta-{index}",
                title=f"Pasta {index}",
                path=f"data/recipes/pasta-{index}.md",
                source_url=None,
            )
            for index in range(30)
        ]
    )
    cog = WeekCommands(api_client)

    choices = asyncio.run(
        cog.recipe_autocomplete(
            MagicMock(),
            "pasta",
        )
    )

    api_client.search_recipes.assert_awaited_once_with(
        "pasta",
        limit=25,
    )
    assert len(choices) == 25
    assert choices[0].name == "Pasta 0"
    assert choices[0].value == "pasta-0"


def test_recipe_autocomplete_skips_blank_query() -> None:
    api_client = MagicMock()
    api_client.search_recipes = AsyncMock()
    cog = WeekCommands(api_client)

    choices = asyncio.run(
        cog.recipe_autocomplete(
            MagicMock(),
            "   ",
        )
    )

    assert choices == []
    api_client.search_recipes.assert_not_awaited()
