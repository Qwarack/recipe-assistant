import logging

import discord
import httpx

from app.bot.api_client import RecipeApiClient
from app.bot.embeds import build_recipe_import_embed

logger = logging.getLogger(__name__)


class RecipeImportView(discord.ui.View):
    def __init__(
        self,
        *,
        api_client: RecipeApiClient,
        source_url: str,
        owner_id: int,
        timeout: float = 300,
    ) -> None:
        super().__init__(timeout=timeout)

        self.api_client = api_client
        self.source_url = source_url
        self.owner_id = owner_id
        self.message: discord.InteractionMessage | None = None

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ) -> bool:
        if interaction.user.id == self.owner_id:
            return True

        await interaction.response.send_message(
            "Alleen de gebruiker die deze import startte mag deze knoppen gebruiken.",
            ephemeral=True,
        )
        return False

    @discord.ui.button(
        label="Opslaan",
        style=discord.ButtonStyle.success,
    )
    async def save_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await interaction.response.defer(
            thinking=True,
            ephemeral=True,
        )

        self._disable_all_buttons()

        try:
            result = await self.api_client.import_website_recipe(self.source_url)
        except httpx.HTTPStatusError as exc:
            await interaction.followup.send(
                (
                    "Het recept kon niet worden opgeslagen. "
                    f"De API gaf status {exc.response.status_code}."
                ),
                ephemeral=True,
            )
            return
        except httpx.HTTPError:
            logger.exception("Saving Discord recipe import failed")
            await interaction.followup.send(
                "De recepten-API is momenteel niet bereikbaar.",
                ephemeral=True,
            )
            return

        embed = build_recipe_import_embed(result)

        await interaction.message.edit(
            embed=embed,
            view=self,
        )

        await interaction.followup.send(
            "Het recept is opgeslagen.",
            ephemeral=True,
        )

        self.stop()

    @discord.ui.button(
        label="Annuleren",
        style=discord.ButtonStyle.secondary,
    )
    async def cancel_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        self._disable_all_buttons()

        await interaction.response.edit_message(
            content="Import geannuleerd.",
            embed=None,
            view=self,
        )

        self.stop()

    async def on_timeout(self) -> None:
        self._disable_all_buttons()

        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                logger.exception("Could not disable timed-out recipe import view")

    def _disable_all_buttons(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
