from app.bot.main import create_bot
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
