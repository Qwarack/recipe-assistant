import logging

import discord
import httpx
from discord import app_commands
from discord.ext import commands

from app.bot.api_client import RecipeApiClient, RecipeImportResponse
from app.bot.embeds import build_recipe_import_embed
from app.bot.modals import ManualRecipeModal
from app.bot.views import RecipeImportView
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

        async def save_website(
            force: bool,
        ) -> RecipeImportResponse:
            return await api_client.import_website_recipe(
                url,
                force=force,
            )

        view = RecipeImportView(
            api_client=api_client,
            import_action=save_website,
            owner_id=interaction.user.id,
        )

        message = await interaction.followup.send(
            embed=embed,
            view=view,
            ephemeral=True,
            wait=True,
        )

        view.message = message

    @recipe_group.command(
        name="tekst",
        description="Importeer een handmatig geplakt recept",
    )
    async def import_recipe_text(
        interaction: discord.Interaction,
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

        modal = ManualRecipeModal(
            api_client=api_client,
            owner_id=interaction.user.id,
        )

        await interaction.response.send_modal(modal)

    @recipe_group.command(
        name="zoek",
        description="Zoek in opgeslagen recepten",
    )
    @app_commands.describe(
        query="Zoekterm, bijvoorbeeld pasta of vegetarisch",
    )
    async def search_recipe(
        interaction: discord.Interaction,
        query: str,
    ) -> None:
        if (
            settings.discord_allowed_channel_id is not None
            and interaction.channel_id != settings.discord_allowed_channel_id
        ):
            await interaction.response.send_message(
                "Dit commando mag alleen in het "
                "ingestelde receptenkanaal worden gebruikt.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(
            thinking=True,
            ephemeral=True,
        )

        try:
            results = await api_client.search_recipes(
                query,
                limit=10,
            )
        except httpx.HTTPStatusError as exc:
            await interaction.followup.send(
                (
                    "De zoekopdracht kon niet worden verwerkt. "
                    f"De API gaf status {exc.response.status_code}."
                ),
                ephemeral=True,
            )
            return
        except httpx.HTTPError:
            logger.exception("Discord recipe search request failed")
            await interaction.followup.send(
                "De recepten-API is momenteel niet bereikbaar.",
                ephemeral=True,
            )
            return

        if not results:
            await interaction.followup.send(
                f"Geen recepten gevonden voor **{query}**.",
                ephemeral=True,
            )
            return

        lines: list[str] = []

        for result in results:
            if result.source_url is not None:
                lines.append(f"• [{result.title}]({result.source_url})")
            else:
                lines.append(f"• **{result.title}**")

        embed = discord.Embed(
            title=f"Zoekresultaten voor: {query}",
            description="\n".join(lines),
        )

        embed.set_footer(text=f"{len(results)} resultaat/resultaten")

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
