import logging

import discord
import httpx

from app.bot.api_client import RecipeApiClient, RecipeImportResponse
from app.bot.embeds import build_recipe_import_embed
from app.bot.views import RecipeImportView

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
            ephemeral=True,
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
                ephemeral=True,
            )
            return
        except httpx.HTTPError:
            logger.exception("Manual recipe preview request failed")
            await interaction.followup.send(
                "De recepten-API is momenteel niet bereikbaar.",
                ephemeral=True,
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

        view = RecipeImportView(
            api_client=self.api_client,
            import_action=save_manual,
            owner_id=self.owner_id,
        )

        message = await interaction.followup.send(
            embed=embed,
            view=view,
            ephemeral=True,
            wait=True,
        )

        view.message = message
