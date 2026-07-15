import logging

import discord
from discord.ext import commands

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def create_bot() -> commands.Bot:
    intents = discord.Intents.default()

    bot = commands.Bot(
        command_prefix="!",
        intents=intents,
    )

    @bot.event
    async def on_ready() -> None:
        if bot.user is None:
            logger.warning("Discord bot connected without user information")
            return

        logger.info(
            "Discord bot connected as %s (%s)",
            bot.user,
            bot.user.id,
        )

    return bot


def main() -> None:
    settings = get_settings()

    if not settings.discord_bot_token:
        raise RuntimeError("DISCORD_BOT_TOKEN is required to start the Discord bot.")

    bot = create_bot()
    bot.run(settings.discord_bot_token)


if __name__ == "__main__":
    main()
