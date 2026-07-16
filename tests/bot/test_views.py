import asyncio
from unittest.mock import AsyncMock, MagicMock

import discord
from app.bot.api_client import RecipeApiClient, RecipeImportResponse
from app.bot.views import (
    DetectedUrlView,
    DuplicateRecipeView,
    RecipeDeleteView,
    RecipeImportView,
)


async def unexpected_import(force: bool) -> RecipeImportResponse:
    raise AssertionError("Import action should not be called")


def test_recipe_import_view_contains_save_and_cancel_buttons() -> None:
    view = RecipeImportView(
        api_client=RecipeApiClient(base_url="http://example.test"),
        import_action=unexpected_import,
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
        import_action=unexpected_import,
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
    import_action = AsyncMock(
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
        import_action=import_action,
        owner_id=123,
    )
    interaction = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    interaction.followup.send = AsyncMock()
    interaction.message.edit = AsyncMock()

    asyncio.run(view.save_button.callback(interaction))

    interaction.response.defer.assert_awaited_once_with()
    import_action.assert_awaited_once_with(False)
    interaction.edit_original_response.assert_awaited_once()
    interaction.message.edit.assert_not_awaited()


def test_duplicate_recipe_view_contains_force_save_and_cancel_buttons() -> None:
    view = DuplicateRecipeView(
        api_client=RecipeApiClient(base_url="http://example.test"),
        import_action=unexpected_import,
        owner_id=123,
    )

    buttons = [child for child in view.children if isinstance(child, discord.ui.Button)]

    assert [button.label for button in buttons] == [
        "Toch opnieuw opslaan",
        "Niet opslaan",
    ]


def test_force_save_button_imports_with_force_enabled() -> None:
    api_client = RecipeApiClient(base_url="http://example.test")
    import_action = AsyncMock(
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
        import_action=import_action,
        owner_id=123,
    )
    interaction = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    interaction.followup.send = AsyncMock()

    asyncio.run(view.force_save_button.callback(interaction))

    import_action.assert_awaited_once_with(True)
    interaction.response.defer.assert_awaited_once_with()
    interaction.edit_original_response.assert_awaited_once()


def test_save_button_shows_duplicate_view_for_strong_duplicate() -> None:
    api_client = RecipeApiClient(base_url="http://example.test")
    import_action = AsyncMock(
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
        import_action=import_action,
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
    import_action = AsyncMock(
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
        import_action=import_action,
        owner_id=123,
    )
    interaction = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    interaction.followup.send = AsyncMock()

    asyncio.run(view.save_button.callback(interaction))

    edit_kwargs = interaction.edit_original_response.await_args.kwargs

    assert edit_kwargs["view"] is view


def test_recipe_delete_view_contains_confirmation_buttons() -> None:
    view = RecipeDeleteView(
        api_client=RecipeApiClient(base_url="http://example.test"),
        identifier="pasta-carbonara",
        recipe_title="Pasta Carbonara",
        owner_id=123,
    )

    buttons = [child for child in view.children if isinstance(child, discord.ui.Button)]

    assert [button.label for button in buttons] == [
        "Definitief verwijderen",
        "Annuleren",
    ]

    assert buttons[0].style is discord.ButtonStyle.danger


def test_confirm_delete_edits_ephemeral_interaction_response() -> None:
    api_client = MagicMock()
    api_client.delete_recipe = AsyncMock()
    view = RecipeDeleteView(
        api_client=api_client,
        identifier="pasta-carbonara",
        recipe_title="Pasta Carbonara",
        owner_id=123,
    )
    interaction = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    interaction.message.edit = AsyncMock()

    asyncio.run(view.confirm_delete.callback(interaction))

    interaction.response.defer.assert_awaited_once_with(
        thinking=True,
        ephemeral=True,
    )
    api_client.delete_recipe.assert_awaited_once_with("pasta-carbonara")
    interaction.edit_original_response.assert_awaited_once_with(
        content="**Pasta Carbonara** is verwijderd.",
        embed=None,
        view=view,
    )
    interaction.message.edit.assert_not_awaited()


def test_detected_url_view_contains_preview_button() -> None:
    view = DetectedUrlView(
        api_client=RecipeApiClient(base_url="http://example.test"),
        source_url="https://example.com/pasta",
        owner_id=123,
    )

    buttons = [child for child in view.children if isinstance(child, discord.ui.Button)]

    assert len(buttons) == 1
    assert buttons[0].label == "Preview maken"
    assert buttons[0].style is discord.ButtonStyle.primary


def test_detected_url_view_sends_public_preview() -> None:
    preview_result = RecipeImportResponse(
        import_id="preview-id",
        status="success",
        destination=None,
        recipe=None,
        warnings=[],
    )
    api_client = MagicMock()
    api_client.preview_website_recipe = AsyncMock(return_value=preview_result)
    view = DetectedUrlView(
        api_client=api_client,
        source_url="https://example.com/pasta",
        owner_id=123,
    )
    interaction = MagicMock()
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock(return_value=MagicMock())
    interaction.message = None

    asyncio.run(view.preview_button.callback(interaction))

    interaction.response.defer.assert_awaited_once_with(
        thinking=True,
        ephemeral=False,
    )
    send_kwargs = interaction.followup.send.await_args.kwargs

    assert isinstance(send_kwargs["view"], RecipeImportView)
    assert send_kwargs["ephemeral"] is False
    assert send_kwargs["wait"] is True
