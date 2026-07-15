import logging

import discord
import httpx
from discord import app_commands
from discord.ext import commands

from app.bot.api_client import RecipeApiClient
from app.bot.embeds import build_recipe_import_embed
from app.core.config import get_settings
from app.core.logging import configure_logging

logger = logging.getLogger(__name__)


def create_bot() -> commands.Bot:
    settings = get_settings()
    intents = discord.Intents.default()
    intents.message_content = True

    bot = commands.Bot(
        command_prefix="!",
        intents=intents,
    )

    api_client = RecipeApiClient(base_url=settings.api_base_url)

    recipe_group = app_commands.Group(
        name="recept",
        description="Beheer recepten",
    )

    @recipe_group.command(
        name="import",
        description="Importeer een recept vanaf een website",
    )
    @app_commands.describe(
        url="URL van de receptenpagina",
    )
    async def import_recipe(
        interaction: discord.Interaction,
        url: str,
    ) -> None:
        if (
            settings.discord_allowed_channel_id is not None
            and interaction.channel_id != settings.discord_allowed_channel_id
        ):
            await interaction.response.send_message(
                (
                    "Dit commando mag alleen in het ingestelde "
                    "receptenkanaal worden gebruikt."
                ),
                ephemeral=True,
            )
            return

        await interaction.response.defer(
            thinking=True,
            ephemeral=True,
        )

        try:
            result = await api_client.preview_website_recipe(url)
        except httpx.HTTPStatusError as exc:
            await interaction.followup.send(
                (
                    "De import kon niet worden verwerkt. "
                    f"De API gaf status {exc.response.status_code}."
                ),
                ephemeral=True,
            )
            return
        except httpx.HTTPError:
            logger.exception("Discord recipe import request failed")
            await interaction.followup.send(
                "De recepten-API is momenteel niet bereikbaar.",
                ephemeral=True,
            )
            return

        embed = build_recipe_import_embed(result)

        await interaction.followup.send(
            embed=embed,
            ephemeral=True,
        )

    bot.tree.add_command(recipe_group)

    @bot.event
    async def on_ready() -> None:
        if bot.user is None:
            logger.warning("Discord bot connected without user information")
            return

        if settings.discord_guild_id is not None:
            guild = discord.Object(id=settings.discord_guild_id)

            bot.tree.copy_global_to(guild=guild)
            synced = await bot.tree.sync(guild=guild)

            logger.info(
                "Synced %s Discord commands to guild %s",
                len(synced),
                settings.discord_guild_id,
            )
        else:
            synced = await bot.tree.sync()

            logger.info(
                "Synced %s global Discord commands",
                len(synced),
            )

        logger.info(
            "Discord bot connected as %s (%s)",
            bot.user,
            bot.user.id,
        )

    return bot


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)

    if not settings.discord_bot_token:
        raise RuntimeError("DISCORD_BOT_TOKEN is required to start the Discord bot.")

    bot = create_bot()
    bot.run(settings.discord_bot_token)


if __name__ == "__main__":
    main()
