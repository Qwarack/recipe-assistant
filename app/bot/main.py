import logging
from pathlib import Path

import discord
import httpx
from discord import app_commands
from discord.ext import commands

from app.bot.api_client import RecipeApiClient, RecipeImportResponse
from app.bot.attachments import validate_recipe_attachment
from app.bot.checks import ensure_allowed_channel, ensure_allowed_role
from app.bot.embeds import build_recipe_detail_embed, build_recipe_import_embed
from app.bot.errors import handle_app_command_error
from app.bot.modals import ManualRecipeModal
from app.bot.url_utils import extract_first_url
from app.bot.views import RecipeDeleteView, RecipeImportView
from app.core.config import get_settings
from app.core.logging import configure_logging

logger = logging.getLogger(__name__)

EPHERMAL_RESPONSE = False  # Set to True to make bot responses only visible to the user


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
    @app_commands.checks.cooldown(
        2,
        60.0,
        key=lambda interaction: interaction.user.id,
    )
    async def import_recipe(
        interaction: discord.Interaction,
        url: str,
    ) -> None:
        if not await ensure_allowed_channel(
            interaction,
            settings.discord_allowed_channel_id,
        ):
            return

        if not await ensure_allowed_role(
            interaction,
            settings.allowed_discord_role_ids,
        ):
            return

        await interaction.response.defer(
            thinking=True,
            ephemeral=EPHERMAL_RESPONSE,
        )

        try:
            result = await api_client.preview_website_recipe(url)
        except httpx.HTTPStatusError as exc:
            await interaction.followup.send(
                (
                    "De import kon niet worden verwerkt. "
                    f"De API gaf status {exc.response.status_code}."
                ),
                ephemeral=EPHERMAL_RESPONSE,
            )
            return
        except httpx.HTTPError:
            logger.exception("Discord recipe import request failed")
            await interaction.followup.send(
                "De recepten-API is momenteel niet bereikbaar.",
                ephemeral=EPHERMAL_RESPONSE,
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
            ephemeral=EPHERMAL_RESPONSE,
            wait=True,
        )

        view.message = message

    @import_recipe.error
    async def import_recipe_error(
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        await handle_app_command_error(
            interaction,
            error,
        )

    @recipe_group.command(
        name="tekst",
        description="Importeer een handmatig geplakt recept",
    )
    @app_commands.checks.cooldown(
        2,
        60.0,
        key=lambda interaction: interaction.user.id,
    )
    async def import_recipe_text(
        interaction: discord.Interaction,
    ) -> None:
        if not await ensure_allowed_channel(
            interaction,
            settings.discord_allowed_channel_id,
        ):
            return

        if not await ensure_allowed_role(
            interaction,
            settings.allowed_discord_role_ids,
        ):
            return

        modal = ManualRecipeModal(
            api_client=api_client,
            owner_id=interaction.user.id,
        )

        await interaction.response.send_modal(modal)

    @import_recipe_text.error
    async def import_recipe_text_error(
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        await handle_app_command_error(
            interaction,
            error,
        )

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
        if not await ensure_allowed_channel(
            interaction,
            settings.discord_allowed_channel_id,
        ):
            return

        await interaction.response.defer(
            thinking=True,
            ephemeral=EPHERMAL_RESPONSE,
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
                ephemeral=EPHERMAL_RESPONSE,
            )
            return
        except httpx.HTTPError:
            logger.exception("Discord recipe search request failed")
            await interaction.followup.send(
                "De recepten-API is momenteel niet bereikbaar.",
                ephemeral=EPHERMAL_RESPONSE,
            )
            return

        if not results:
            await interaction.followup.send(
                f"Geen recepten gevonden voor **{query}**.",
                ephemeral=EPHERMAL_RESPONSE,
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
            ephemeral=EPHERMAL_RESPONSE,
        )

    @recipe_group.command(
        name="toon",
        description="Toon een opgeslagen recept",
    )
    @app_commands.describe(
        identifier="Recept-ID, bijvoorbeeld pasta-carbonara",
    )
    async def show_recipe(
        interaction: discord.Interaction,
        identifier: str,
    ) -> None:
        if not await ensure_allowed_channel(
            interaction,
            settings.discord_allowed_channel_id,
        ):
            return

        await interaction.response.defer(
            thinking=True,
            ephemeral=EPHERMAL_RESPONSE,
        )

        try:
            recipe = await api_client.get_recipe(identifier)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                await interaction.followup.send(
                    f"Geen recept gevonden met ID `{identifier}`.",
                    ephemeral=EPHERMAL_RESPONSE,
                )
                return

            await interaction.followup.send(
                (
                    "Het recept kon niet worden opgehaald. "
                    f"De API gaf status {exc.response.status_code}."
                ),
                ephemeral=EPHERMAL_RESPONSE,
            )
            return
        except httpx.HTTPError:
            logger.exception("Discord recipe detail request failed")
            await interaction.followup.send(
                "De recepten-API is momenteel niet bereikbaar.",
                ephemeral=EPHERMAL_RESPONSE,
            )
            return

        embed = build_recipe_detail_embed(recipe)

        await interaction.followup.send(
            embed=embed,
            ephemeral=EPHERMAL_RESPONSE,
        )

    @show_recipe.autocomplete("identifier")
    async def recipe_identifier_autocomplete(
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        try:
            results = await api_client.search_recipes(
                current,
                limit=25,
            )
        except httpx.HTTPError:
            logger.exception("Discord recipe autocomplete request failed")
            return []

        return [
            app_commands.Choice(
                name=result.title[:100],
                value=Path(result.path).stem[:100],
            )
            for result in results
        ]

    @recipe_group.command(
        name="verwijder",
        description="Verwijder een opgeslagen recept",
    )
    @app_commands.describe(
        identifier="Het recept dat je wilt verwijderen",
    )
    async def delete_recipe_command(
        interaction: discord.Interaction,
        identifier: str,
    ) -> None:
        if not await ensure_allowed_channel(
            interaction,
            settings.discord_allowed_channel_id,
        ):
            return

        if not await ensure_allowed_role(
            interaction,
            settings.allowed_discord_role_ids,
        ):
            return

        await interaction.response.defer(
            thinking=True,
            ephemeral=EPHERMAL_RESPONSE,
        )

        try:
            recipe = await api_client.get_recipe(identifier)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                await interaction.followup.send(
                    f"Geen recept gevonden met ID `{identifier}`.",
                    ephemeral=EPHERMAL_RESPONSE,
                )
                return

            await interaction.followup.send(
                (
                    "Het recept kon niet worden opgehaald. "
                    f"De API gaf status {exc.response.status_code}."
                ),
                ephemeral=EPHERMAL_RESPONSE,
            )
            return
        except httpx.HTTPError:
            logger.exception("Discord recipe delete preview failed")
            await interaction.followup.send(
                "De recepten-API is momenteel niet bereikbaar.",
                ephemeral=EPHERMAL_RESPONSE,
            )
            return

        logger.info(
            "Discord recipe delete requested",
            extra={
                "recipe_identifier": recipe.identifier,
                "recipe_title": recipe.title,
                "discord_user_id": interaction.user.id,
                "discord_user_name": str(interaction.user),
                "discord_guild_id": interaction.guild_id,
                "discord_channel_id": interaction.channel_id,
            },
        )

        view = RecipeDeleteView(
            api_client=api_client,
            identifier=recipe.identifier,
            recipe_title=recipe.title,
            owner_id=interaction.user.id,
        )

        await interaction.followup.send(
            content=(
                f"Weet je zeker dat je **{recipe.title}** definitief wilt verwijderen?"
            ),
            view=view,
            ephemeral=EPHERMAL_RESPONSE,
        )

    @delete_recipe_command.autocomplete("identifier")
    async def delete_recipe_autocomplete(
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        try:
            results = await api_client.search_recipes(
                current,
                limit=25,
            )
        except httpx.HTTPError:
            logger.exception("Discord recipe delete autocomplete failed")
            return []

        return [
            app_commands.Choice(
                name=result.title[:100],
                value=Path(result.path).stem[:100],
            )
            for result in results
        ]

    @recipe_group.command(
        name="upload",
        description="Importeer een receptbestand",
    )
    @app_commands.describe(
        bestand="Markdown-, tekst- of HTML-bestand",
    )
    @app_commands.checks.cooldown(
        2,
        60.0,
        key=lambda interaction: interaction.user.id,
    )
    async def upload_recipe(
        interaction: discord.Interaction,
        bestand: discord.Attachment,
    ) -> None:
        if not await ensure_allowed_channel(
            interaction,
            settings.discord_allowed_channel_id,
        ):
            return

        if not await ensure_allowed_role(
            interaction,
            settings.allowed_discord_role_ids,
        ):
            return

        validation = validate_recipe_attachment(
            filename=bestand.filename,
            size_bytes=bestand.size,
        )

        if not validation.valid:
            await interaction.response.send_message(
                validation.error or "Ongeldig bestand.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(
            thinking=True,
            ephemeral=True,
        )

        try:
            content = await bestand.read()

            result = await api_client.preview_uploaded_recipe(
                filename=bestand.filename,
                content=content,
                content_type=bestand.content_type,
            )
        except discord.HTTPException:
            logger.exception("Downloading Discord recipe attachment failed")
            await interaction.followup.send(
                "Het bestand kon niet van Discord worden gedownload.",
                ephemeral=True,
            )
            return
        except httpx.HTTPStatusError as exc:
            await interaction.followup.send(
                (
                    "Het bestand kon niet worden verwerkt. "
                    f"De API gaf status {exc.response.status_code}."
                ),
                ephemeral=True,
            )
            return
        except httpx.HTTPError:
            logger.exception("Recipe upload preview request failed")
            await interaction.followup.send(
                "De recepten-API is momenteel niet bereikbaar.",
                ephemeral=True,
            )
            return

        embed = build_recipe_import_embed(result)

        async def save_upload(
            force: bool,
        ) -> RecipeImportResponse:
            return await api_client.import_uploaded_recipe(
                filename=bestand.filename,
                content=content,
                content_type=bestand.content_type,
                force=force,
            )

        view = RecipeImportView(
            api_client=api_client,
            import_action=save_upload,
            owner_id=interaction.user.id,
        )

        message = await interaction.followup.send(
            embed=embed,
            view=view,
            ephemeral=True,
            wait=True,
        )

        view.message = message

    @upload_recipe.error
    async def upload_recipe_error(
        interaction: discord.Interaction,
        error: app_commands.AppCommandError,
    ) -> None:
        await handle_app_command_error(
            interaction,
            error,
        )

    bot.tree.add_command(recipe_group)

    @bot.event
    async def on_message(
        message: discord.Message,
    ) -> None:
        if message.author.bot:
            return

        if (
            settings.discord_allowed_channel_id is not None
            and message.channel.id != settings.discord_allowed_channel_id
        ):
            return

        url = extract_first_url(message.content)

        if url is None:
            return

        await message.reply(
            (
                "Ik heb een URL gevonden. "
                "Gebruik `/recept import` om eerst een preview te bekijken."
            ),
            mention_author=False,
        )

        await bot.process_commands(message)

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
