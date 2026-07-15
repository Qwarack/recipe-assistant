import asyncio
from unittest.mock import AsyncMock, MagicMock

import discord
from app.bot.api_client import RecipeApiClient, RecipeImportResponse
from app.bot.views import DuplicateRecipeView, RecipeImportView


def test_recipe_import_view_contains_save_and_cancel_buttons() -> None:
    view = RecipeImportView(
        api_client=RecipeApiClient(base_url="http://example.test"),
        source_url="https://example.com/pasta",
        owner_id=123,
    )

    buttons = [child for child in view.children if isinstance(child, discord.ui.Button)]

    assert [button.label for button in buttons] == [
        "Opslaan",
        "Annuleren",
    ]


def test_disable_all_buttons() -> None:
    view = RecipeImportView(
        api_client=RecipeApiClient(base_url="http://example.test"),
        source_url="https://example.com/pasta",
        owner_id=123,
    )

    view._disable_all_buttons()

    assert all(
        child.disabled
        for child in view.children
        if isinstance(child, discord.ui.Button)
    )


def test_save_button_edits_ephemeral_interaction_response() -> None:
    api_client = RecipeApiClient(base_url="http://example.test")
    api_client.import_website_recipe = AsyncMock(
        return_value=RecipeImportResponse(
            import_id="abc123",
            status="success",
            destination="/data/recipes/pasta.md",
            recipe=None,
            warnings=[],
        )
    )
    view = RecipeImportView(
        api_client=api_client,
        source_url="https://example.com/pasta",
        owner_id=123,
    )
    interaction = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    interaction.followup.send = AsyncMock()
    interaction.message.edit = AsyncMock()

    asyncio.run(view.save_button.callback(interaction))

    interaction.response.defer.assert_awaited_once_with()
    interaction.edit_original_response.assert_awaited_once()
    interaction.message.edit.assert_not_awaited()


def test_duplicate_recipe_view_contains_force_save_and_cancel_buttons() -> None:
    view = DuplicateRecipeView(
        api_client=RecipeApiClient(base_url="http://example.test"),
        source_url="https://example.com/pasta",
        owner_id=123,
    )

    buttons = [child for child in view.children if isinstance(child, discord.ui.Button)]

    assert [button.label for button in buttons] == [
        "Toch opnieuw opslaan",
        "Niet opslaan",
    ]


def test_force_save_button_imports_with_force_enabled() -> None:
    api_client = RecipeApiClient(base_url="http://example.test")
    api_client.import_website_recipe = AsyncMock(
        return_value=RecipeImportResponse(
            import_id="abc123",
            status="success",
            destination="/data/recipes/pasta-copy.md",
            recipe=None,
            warnings=[],
        )
    )
    view = DuplicateRecipeView(
        api_client=api_client,
        source_url="https://example.com/pasta",
        owner_id=123,
    )
    interaction = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    interaction.followup.send = AsyncMock()

    asyncio.run(view.force_save_button.callback(interaction))

    api_client.import_website_recipe.assert_awaited_once_with(
        "https://example.com/pasta",
        force=True,
    )
    interaction.response.defer.assert_awaited_once_with()
    interaction.edit_original_response.assert_awaited_once()


def test_save_button_shows_duplicate_view_for_strong_duplicate() -> None:
    api_client = RecipeApiClient(base_url="http://example.test")
    api_client.import_website_recipe = AsyncMock(
        return_value=RecipeImportResponse(
            import_id="abc123",
            status="partial",
            destination="/data/recipes/pasta.md",
            recipe=None,
            warnings=[
                {
                    "code": "duplicate_source_url",
                    "message": "Recipe already exists.",
                }
            ],
        )
    )
    view = RecipeImportView(
        api_client=api_client,
        source_url="https://example.com/pasta",
        owner_id=123,
    )
    interaction = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    interaction.followup.send = AsyncMock()

    asyncio.run(view.save_button.callback(interaction))

    edit_kwargs = interaction.edit_original_response.await_args.kwargs

    assert isinstance(edit_kwargs["view"], DuplicateRecipeView)


def test_save_button_does_not_show_duplicate_view_for_title_warning() -> None:
    api_client = RecipeApiClient(base_url="http://example.test")
    api_client.import_website_recipe = AsyncMock(
        return_value=RecipeImportResponse(
            import_id="abc123",
            status="partial",
            destination="/data/recipes/pasta-copy.md",
            recipe=None,
            warnings=[
                {
                    "code": "duplicate_title",
                    "message": "A recipe with a similar title exists.",
                }
            ],
        )
    )
    view = RecipeImportView(
        api_client=api_client,
        source_url="https://example.com/pasta",
        owner_id=123,
    )
    interaction = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    interaction.followup.send = AsyncMock()

    asyncio.run(view.save_button.callback(interaction))

    edit_kwargs = interaction.edit_original_response.await_args.kwargs

    assert edit_kwargs["view"] is view
