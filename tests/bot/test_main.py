import asyncio
from unittest.mock import AsyncMock, MagicMock

import discord
from app.bot.api_client import RecipeImportResponse
from app.bot.main import create_bot
from app.bot.views import RecipeImportView
from app.core.config import Settings
from discord.ext import commands


def test_create_bot_returns_discord_bot() -> None:
    bot = create_bot()

    assert isinstance(bot, commands.Bot)


def test_create_bot_registers_recipe_group() -> None:
    bot = create_bot()

    command = bot.tree.get_command("recept")

    assert command is not None
    assert command.name == "recept"

    text_command = command.get_command("tekst")

    assert text_command is not None
    assert text_command.name == "tekst"


def test_import_commands_have_cooldown_and_error_handler() -> None:
    bot = create_bot()
    recipe_group = bot.tree.get_command("recept")

    for command_name in ("import", "tekst", "upload"):
        command = recipe_group.get_command(command_name)

        assert len(command.checks) == 1
        assert command.on_error is not None


def test_delete_command_rejects_member_before_deferring(monkeypatch) -> None:
    settings = Settings(
        _env_file=None,
        discord_allowed_role_ids="123",
    )
    monkeypatch.setattr("app.bot.main.get_settings", lambda: settings)
    bot = create_bot()
    recipe_group = bot.tree.get_command("recept")
    delete_command = recipe_group.get_command("verwijder")
    interaction = MagicMock()
    interaction.channel_id = None
    interaction.user = MagicMock(spec=discord.Member)
    interaction.user.roles = [MagicMock(id=456)]
    interaction.response.send_message = AsyncMock()
    interaction.response.defer = AsyncMock()

    asyncio.run(delete_command.callback(interaction, "pasta-carbonara"))

    interaction.response.send_message.assert_awaited_once_with(
        "Je hebt geen toestemming om recepten te verwijderen.",
        ephemeral=True,
    )
    interaction.response.defer.assert_not_awaited()


def test_delete_command_accepts_configured_role_id(monkeypatch) -> None:
    settings = Settings(
        _env_file=None,
        discord_allowed_role_ids="123, 456",
    )
    api_client = MagicMock()
    api_client.get_recipe = AsyncMock(
        return_value=MagicMock(
            identifier="pasta-carbonara",
            title="Pasta Carbonara",
        )
    )
    monkeypatch.setattr("app.bot.main.get_settings", lambda: settings)
    monkeypatch.setattr(
        "app.bot.main.RecipeApiClient",
        MagicMock(return_value=api_client),
    )
    bot = create_bot()
    recipe_group = bot.tree.get_command("recept")
    delete_command = recipe_group.get_command("verwijder")
    interaction = MagicMock()
    interaction.channel_id = None
    interaction.user = MagicMock(spec=discord.Member)
    interaction.user.id = 789
    interaction.user.roles = [MagicMock(id=456)]
    interaction.response.send_message = AsyncMock()
    interaction.response.defer = AsyncMock()
    interaction.followup.send = AsyncMock()

    asyncio.run(delete_command.callback(interaction, "pasta-carbonara"))

    interaction.response.send_message.assert_not_awaited()
    interaction.response.defer.assert_awaited_once_with(
        thinking=True,
        ephemeral=False,
    )
    api_client.get_recipe.assert_awaited_once_with("pasta-carbonara")
    interaction.followup.send.assert_awaited_once()


def test_upload_command_creates_save_view_with_attachment_content(monkeypatch) -> None:
    settings = Settings(_env_file=None)
    preview_result = RecipeImportResponse(
        import_id="preview-id",
        status="success",
        destination=None,
        recipe=None,
        warnings=[],
    )
    import_result = RecipeImportResponse(
        import_id="import-id",
        status="success",
        destination="/data/recipes/pasta.md",
        recipe=None,
        warnings=[],
    )
    api_client = MagicMock()
    api_client.preview_uploaded_recipe = AsyncMock(return_value=preview_result)
    api_client.import_uploaded_recipe = AsyncMock(return_value=import_result)
    monkeypatch.setattr("app.bot.main.get_settings", lambda: settings)
    monkeypatch.setattr(
        "app.bot.main.RecipeApiClient",
        MagicMock(return_value=api_client),
    )
    bot = create_bot()
    recipe_group = bot.tree.get_command("recept")
    upload_command = recipe_group.get_command("upload")
    interaction = MagicMock()
    interaction.channel_id = None
    interaction.user.id = 123
    interaction.response.defer = AsyncMock()
    confirmation_message = MagicMock()
    interaction.followup.send = AsyncMock(return_value=confirmation_message)
    attachment = MagicMock(spec=discord.Attachment)
    attachment.filename = "pasta.md"
    attachment.size = 18
    attachment.content_type = "text/markdown"
    attachment.read = AsyncMock(return_value=b"# Pasta Carbonara")

    asyncio.run(upload_command.callback(interaction, attachment))

    api_client.preview_uploaded_recipe.assert_awaited_once_with(
        filename="pasta.md",
        content=b"# Pasta Carbonara",
        content_type="text/markdown",
    )
    send_kwargs = interaction.followup.send.await_args.kwargs
    view = send_kwargs["view"]

    assert isinstance(view, RecipeImportView)
    assert send_kwargs["ephemeral"] is True
    assert send_kwargs["wait"] is True
    assert view.message is confirmation_message

    result = asyncio.run(view.import_action(True))

    assert result is import_result
    api_client.import_uploaded_recipe.assert_awaited_once_with(
        filename="pasta.md",
        content=b"# Pasta Carbonara",
        content_type="text/markdown",
        force=True,
    )
