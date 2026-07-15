import asyncio
from unittest.mock import AsyncMock, MagicMock

import discord
from app.bot.api_client import RecipeApiClient, RecipeImportResponse
from app.bot.modals import ManualRecipeModal
from app.bot.views import RecipeImportView


def test_manual_recipe_modal_contains_paragraph_text_input() -> None:
    modal = ManualRecipeModal(
        api_client=RecipeApiClient(base_url="http://example.test"),
        owner_id=123,
    )

    assert modal.title == "Recept invoeren"
    assert modal.recipe_text.label == "Recepttekst"
    assert modal.recipe_text.style == discord.TextStyle.paragraph
    assert modal.recipe_text.min_length == 20
    assert modal.recipe_text.max_length == 4000


def test_manual_recipe_modal_previews_and_builds_manual_save_action() -> None:
    recipe_text = """Soup

Ingrediënten:
- water

Bereiding:
1. Meng alles.
"""
    api_client = RecipeApiClient(base_url="http://example.test")
    api_client.preview_manual_recipe = AsyncMock(
        return_value=RecipeImportResponse(
            import_id="abc123",
            status="success",
            destination=None,
            recipe=None,
            warnings=[],
        )
    )
    api_client.import_manual_recipe = AsyncMock(
        return_value=RecipeImportResponse(
            import_id="def456",
            status="success",
            destination="/data/recipes/soup.md",
            recipe=None,
            warnings=[],
        )
    )
    modal = ManualRecipeModal(
        api_client=api_client,
        owner_id=123,
    )
    modal.recipe_text._value = recipe_text
    interaction = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock(return_value=MagicMock())

    asyncio.run(modal.on_submit(interaction))

    api_client.preview_manual_recipe.assert_awaited_once_with(recipe_text)
    interaction.response.defer.assert_awaited_once_with(
        thinking=True,
        ephemeral=True,
    )

    preview_view = interaction.followup.send.await_args.kwargs["view"]

    assert isinstance(preview_view, RecipeImportView)

    asyncio.run(preview_view.import_action(True))

    api_client.import_manual_recipe.assert_awaited_once_with(
        recipe_text,
        force=True,
    )
