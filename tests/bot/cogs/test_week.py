import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock

from app.bot.api_client import MealPlan, RecipeSearchResult
from app.bot.cogs.week import (
    WeekCommands,
    get_planning_start_date,
    parse_weekdays,
)


def test_planning_start_date_for_every_weekday() -> None:
    expected_start = date(2026, 7, 15)

    for day_offset in range(7):
        target_date = date(2026, 7, 15 + day_offset)
        assert get_planning_start_date(target_date) == expected_start


def test_parse_weekdays_accepts_dutch_and_technical_abbreviations() -> None:
    assert parse_weekdays("ma, do,zo") == [0, 3, 6]
    assert parse_weekdays("mon,thu,sun") == [0, 3, 6]


def test_parse_weekdays_rejects_unknown_value() -> None:
    try:
        parse_weekdays("ma,feestdag")
    except ValueError as exc:
        assert "feestdag" in str(exc)
    else:
        raise AssertionError("Expected invalid weekday to fail")


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


def test_update_entry_requires_at_least_one_change() -> None:
    api_client = MagicMock()
    cog = WeekCommands(api_client)
    interaction = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()

    asyncio.run(
        WeekCommands.update_entry.callback(
            cog,
            interaction,
            entry_id=7,
        )
    )

    api_client.update_meal_plan_entry.assert_not_called()
    interaction.followup.send.assert_awaited_once_with(
        "Geef minstens één wijziging op.",
        ephemeral=True,
    )


def test_remove_entry_uses_current_plan_when_start_date_is_omitted() -> None:
    plan = MealPlan(
        id=10,
        start_date=date(2026, 7, 15),
        end_date=date(2026, 7, 21),
        name=None,
        entries=[],
    )
    api_client = MagicMock()
    api_client.get_current_meal_plan = AsyncMock(return_value=plan)
    api_client.remove_meal_plan_entry = AsyncMock(return_value=plan)
    cog = WeekCommands(api_client)
    interaction = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()

    asyncio.run(
        WeekCommands.remove_entry.callback(
            cog,
            interaction,
            entry_id=7,
        )
    )

    api_client.remove_meal_plan_entry.assert_awaited_once_with(
        start_date=date(2026, 7, 15),
        entry_id=7,
    )
