import logging

import discord
import httpx

from app.bot.api_client import RecipeApiClient, RecipeImportResponse
from app.bot.constants import NOTICE_EPHEMERAL, PREVIEW_EPHEMERAL
from app.bot.embeds import build_recipe_import_embed
from app.bot.views import ImportFailedView, RecipeImportView

logger = logging.getLogger(__name__)


class ManualRecipeModal(
    discord.ui.Modal,
    title="Recept invoeren",
):
    recipe_text = discord.ui.TextInput(
        label="Recepttekst",
        placeholder=("Plak hier de titel, ingrediënten en bereidingsstappen..."),
        style=discord.TextStyle.paragraph,
        required=True,
        min_length=20,
        max_length=4000,
    )

    def __init__(
        self,
        *,
        api_client: RecipeApiClient,
        owner_id: int,
    ) -> None:
        super().__init__()

        self.api_client = api_client
        self.owner_id = owner_id

    async def on_submit(
        self,
        interaction: discord.Interaction,
    ) -> None:
        await interaction.response.defer(
            thinking=True,
            ephemeral=PREVIEW_EPHEMERAL,
        )

        recipe_text = str(self.recipe_text)

        try:
            result = await self.api_client.preview_manual_recipe(recipe_text)
        except httpx.HTTPStatusError as exc:
            await interaction.followup.send(
                (
                    "De recepttekst kon niet worden verwerkt. "
                    f"De API gaf status {exc.response.status_code}."
                ),
                ephemeral=NOTICE_EPHEMERAL,
            )
            return
        except httpx.HTTPError:
            logger.exception("Manual recipe preview request failed")
            await interaction.followup.send(
                "De recepten-API is momenteel niet bereikbaar.",
                ephemeral=NOTICE_EPHEMERAL,
            )
            return

        embed = build_recipe_import_embed(result)

        async def save_manual(
            force: bool,
        ) -> RecipeImportResponse:
            return await self.api_client.import_manual_recipe(
                recipe_text,
                force=force,
            )

        async def confirm_import(force: bool) -> RecipeImportResponse:
            return await self.api_client.confirm_import(
                result.import_id,
                force=force,
                discord_user_id=self.owner_id,
            )

        async def parse_with_ai() -> RecipeImportResponse:
            return await self.api_client.parse_import_with_ai(
                result.import_id,
                reason=(
                    "normal_parse_failed"
                    if result.status == "failed"
                    else "user_requested_reparse"
                ),
                discord_user_id=self.owner_id,
            )

        async def cancel_import() -> None:
            await self.api_client.cancel_import(
                result.import_id,
                discord_user_id=self.owner_id,
            )

        if result.status == "failed":
            if not result.ai_enabled:
                await interaction.followup.send(
                    embed=embed,
                    ephemeral=PREVIEW_EPHEMERAL,
                )
                return

            failed_view = ImportFailedView(
                api_client=self.api_client,
                retry_action=parse_with_ai,
                confirm_action=confirm_import,
                cancel_action=cancel_import,
                owner_id=self.owner_id,
            )
            message = await interaction.followup.send(
                embed=embed,
                view=failed_view,
                ephemeral=PREVIEW_EPHEMERAL,
                wait=True,
            )
            failed_view.message = message
            return

        view = RecipeImportView(
            api_client=self.api_client,
            import_action=save_manual,
            owner_id=self.owner_id,
            ai_reparse_action=parse_with_ai if result.ai_enabled else None,
            confirm_action=confirm_import,
            cancel_action=cancel_import if result.ai_enabled else None,
        )

        message = await interaction.followup.send(
            embed=embed,
            view=view,
            ephemeral=PREVIEW_EPHEMERAL,
            wait=True,
        )

        view.message = message
