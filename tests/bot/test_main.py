import asyncio
from unittest.mock import AsyncMock, MagicMock

import discord
from app.bot.main import create_bot
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
