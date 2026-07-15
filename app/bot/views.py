import logging
from collections.abc import Awaitable, Callable

import discord
import httpx

from app.bot.api_client import RecipeApiClient, RecipeImportResponse
from app.bot.embeds import build_recipe_import_embed

logger = logging.getLogger(__name__)

STRONG_DUPLICATE_WARNING_CODES = {
    "duplicate_source_url",
    "duplicate_content",
}

ImportAction = Callable[
    [bool],
    Awaitable[RecipeImportResponse],
]


class RecipeImportView(discord.ui.View):
    def __init__(
        self,
        *,
        api_client: RecipeApiClient,
        import_action: ImportAction,
        owner_id: int,
        timeout: float = 300,
    ) -> None:
        super().__init__(timeout=timeout)

        self.api_client = api_client
        self.import_action = import_action
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
        await interaction.response.defer()

        self._disable_all_buttons()

        try:
            result = await self.import_action(False)
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

        has_duplicate = any(
            warning.get("code") in STRONG_DUPLICATE_WARNING_CODES
            for warning in result.warnings
        )

        if has_duplicate:
            duplicate_view = DuplicateRecipeView(
                api_client=self.api_client,
                import_action=self.import_action,
                owner_id=self.owner_id,
            )
            embed = build_recipe_import_embed(result)

            await interaction.edit_original_response(
                embed=embed,
                view=duplicate_view,
            )
            await interaction.followup.send(
                (
                    "Dit recept lijkt al te bestaan. "
                    "Kies of je toch een nieuwe kopie wilt opslaan."
                ),
                ephemeral=True,
            )

            self.stop()
            return

        embed = build_recipe_import_embed(result)

        await interaction.edit_original_response(
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


class DuplicateRecipeView(discord.ui.View):
    def __init__(
        self,
        *,
        api_client: RecipeApiClient,
        import_action: ImportAction,
        owner_id: int,
        timeout: float = 300,
    ) -> None:
        super().__init__(timeout=timeout)

        self.api_client = api_client
        self.import_action = import_action
        self.owner_id = owner_id

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
        label="Toch opnieuw opslaan",
        style=discord.ButtonStyle.danger,
    )
    async def force_save_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await interaction.response.defer()

        try:
            result = await self.import_action(True)
        except httpx.HTTPStatusError as exc:
            await interaction.followup.send(
                (
                    "Het recept kon niet opnieuw worden opgeslagen. "
                    f"De API gaf status {exc.response.status_code}."
                ),
                ephemeral=True,
            )
            return
        except httpx.HTTPError:
            logger.exception("Force-saving Discord recipe import failed")
            await interaction.followup.send(
                "De recepten-API is momenteel niet bereikbaar.",
                ephemeral=True,
            )
            return

        embed = build_recipe_import_embed(result)

        await interaction.edit_original_response(
            embed=embed,
            view=None,
        )
        await interaction.followup.send(
            "Het recept is opnieuw opgeslagen.",
            ephemeral=True,
        )

        self.stop()

    @discord.ui.button(
        label="Niet opslaan",
        style=discord.ButtonStyle.secondary,
    )
    async def cancel_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await interaction.response.edit_message(
            content="Bestaand recept behouden.",
            embed=None,
            view=None,
        )

        self.stop()
