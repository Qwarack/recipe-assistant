from app.bot.main import create_bot
from discord.ext import commands


def test_create_bot_returns_discord_bot() -> None:
    bot = create_bot()

    assert isinstance(bot, commands.Bot)
