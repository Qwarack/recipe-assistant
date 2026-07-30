import logging
from collections.abc import Awaitable, Callable

import discord
import httpx

from app.bot.api_client import RecipeApiClient, RecipeImportResponse
from app.bot.constants import NOTICE_EPHEMERAL, PREVIEW_EPHEMERAL
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
AIAction = Callable[[], Awaitable[RecipeImportResponse]]
CancelAction = Callable[[], Awaitable[None]]


def _http_error_message(
    error: httpx.HTTPStatusError,
    *,
    fallback: str,
) -> str:
    try:
        detail = error.response.json().get("detail")
    except ValueError:
        return fallback

    if isinstance(detail, str):
        return detail
    if isinstance(detail, dict) and isinstance(detail.get("message"), str):
        return detail["message"]
    return fallback


class RecipeImportView(discord.ui.View):
    def __init__(
        self,
        *,
        api_client: RecipeApiClient,
        import_action: ImportAction,
        owner_id: int,
        ai_reparse_action: AIAction | None = None,
        confirm_action: ImportAction | None = None,
        cancel_action: CancelAction | None = None,
        ai_generated: bool = False,
        timeout: float = 300,
    ) -> None:
        super().__init__(timeout=timeout)

        self.api_client = api_client
        self.import_action = import_action
        self.ai_reparse_action = ai_reparse_action
        self.confirm_action = confirm_action or import_action
        self.cancel_action = cancel_action
        self.owner_id = owner_id
        self.message: discord.InteractionMessage | None = None

        if ai_reparse_action is None:
            self.remove_item(self.ai_reparse_button)
        elif ai_generated:
            self.ai_reparse_button.label = "Opnieuw met AI"

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ) -> bool:
        if interaction.user.id == self.owner_id:
            return True

        await interaction.response.send_message(
            "Alleen de gebruiker die deze import startte mag deze knoppen gebruiken.",
            ephemeral=NOTICE_EPHEMERAL,
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
                ephemeral=NOTICE_EPHEMERAL,
            )
            return
        except httpx.HTTPError:
            logger.exception("Saving Discord recipe import failed")
            await interaction.followup.send(
                "De recepten-API is momenteel niet bereikbaar.",
                ephemeral=NOTICE_EPHEMERAL,
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
                cancel_action=self.cancel_action,
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
                ephemeral=NOTICE_EPHEMERAL,
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
            ephemeral=NOTICE_EPHEMERAL,
        )

        self.stop()

    @discord.ui.button(
        label="Parse met AI",
        style=discord.ButtonStyle.primary,
    )
    async def ai_reparse_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        if self.ai_reparse_action is None:
            return

        await interaction.response.defer(thinking=True)
        self._disable_all_buttons()

        try:
            result = await self.ai_reparse_action()
        except httpx.HTTPStatusError as exc:
            self._enable_all_buttons()
            await interaction.edit_original_response(view=self)
            await interaction.followup.send(
                _http_error_message(
                    exc,
                    fallback=(
                        "Gemma kon dit recept niet verwerken. "
                        "Je kunt het opnieuw proberen."
                    ),
                ),
                ephemeral=NOTICE_EPHEMERAL,
            )
            return
        except httpx.HTTPError:
            self._enable_all_buttons()
            await interaction.edit_original_response(view=self)
            logger.exception("AI recipe reparse request failed")
            await interaction.followup.send(
                "De recepten-API is momenteel niet bereikbaar.",
                ephemeral=NOTICE_EPHEMERAL,
            )
            return

        replacement = RecipeImportView(
            api_client=self.api_client,
            import_action=self.confirm_action,
            owner_id=self.owner_id,
            ai_reparse_action=self.ai_reparse_action,
            confirm_action=self.confirm_action,
            cancel_action=self.cancel_action,
            ai_generated=True,
        )
        replacement.message = self.message

        await interaction.edit_original_response(
            embed=build_recipe_import_embed(result),
            view=replacement,
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

        if self.cancel_action is not None:
            await interaction.response.defer()
            try:
                await self.cancel_action()
            except httpx.HTTPError:
                logger.exception("Cancelling Discord recipe import failed")
                await interaction.followup.send(
                    "De import kon niet bij de recepten-API worden geannuleerd.",
                    ephemeral=NOTICE_EPHEMERAL,
                )
                return

            await interaction.edit_original_response(
                content="Import geannuleerd.",
                embed=None,
                view=self,
            )
            self.stop()
            return

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

    def _enable_all_buttons(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = False


class ImportFailedView(discord.ui.View):
    def __init__(
        self,
        *,
        api_client: RecipeApiClient,
        retry_action: AIAction,
        confirm_action: ImportAction,
        cancel_action: CancelAction,
        owner_id: int,
        timeout: float = 300,
    ) -> None:
        super().__init__(timeout=timeout)
        self.api_client = api_client
        self.retry_action = retry_action
        self.confirm_action = confirm_action
        self.cancel_action = cancel_action
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
            ephemeral=NOTICE_EPHEMERAL,
        )
        return False

    @discord.ui.button(
        label="Opnieuw met AI",
        style=discord.ButtonStyle.primary,
    )
    async def retry_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await interaction.response.defer(thinking=True)
        self._set_disabled(True)

        try:
            result = await self.retry_action()
        except httpx.HTTPStatusError as exc:
            self._set_disabled(False)
            await interaction.edit_original_response(view=self)
            await interaction.followup.send(
                _http_error_message(
                    exc,
                    fallback=(
                        "Gemma kon dit recept niet verwerken. "
                        "Je kunt het opnieuw proberen."
                    ),
                ),
                ephemeral=NOTICE_EPHEMERAL,
            )
            return
        except httpx.HTTPError:
            self._set_disabled(False)
            await interaction.edit_original_response(view=self)
            logger.exception("AI recipe fallback request failed")
            await interaction.followup.send(
                "De recepten-API is momenteel niet bereikbaar.",
                ephemeral=NOTICE_EPHEMERAL,
            )
            return

        replacement = RecipeImportView(
            api_client=self.api_client,
            import_action=self.confirm_action,
            owner_id=self.owner_id,
            ai_reparse_action=self.retry_action,
            confirm_action=self.confirm_action,
            cancel_action=self.cancel_action,
            ai_generated=True,
        )
        replacement.message = self.message
        await interaction.edit_original_response(
            embed=build_recipe_import_embed(result),
            view=replacement,
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
        await interaction.response.defer()
        self._set_disabled(True)

        try:
            await self.cancel_action()
        except httpx.HTTPError:
            logger.exception("Cancelling failed Discord recipe import failed")
            await interaction.followup.send(
                "De import kon niet bij de recepten-API worden geannuleerd.",
                ephemeral=NOTICE_EPHEMERAL,
            )
            return

        await interaction.edit_original_response(
            content="Import geannuleerd.",
            embed=None,
            view=self,
        )
        self.stop()

    async def on_timeout(self) -> None:
        self._set_disabled(True)
        if self.message is not None:
            try:
                await self.message.edit(view=self)
            except discord.HTTPException:
                logger.exception("Could not disable timed-out failed import view")

    def _set_disabled(self, disabled: bool) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = disabled


class DuplicateRecipeView(discord.ui.View):
    def __init__(
        self,
        *,
        api_client: RecipeApiClient,
        import_action: ImportAction,
        owner_id: int,
        cancel_action: CancelAction | None = None,
        timeout: float = 300,
    ) -> None:
        super().__init__(timeout=timeout)

        self.api_client = api_client
        self.import_action = import_action
        self.owner_id = owner_id
        self.cancel_action = cancel_action

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ) -> bool:
        if interaction.user.id == self.owner_id:
            return True

        await interaction.response.send_message(
            "Alleen de gebruiker die deze import startte mag deze knoppen gebruiken.",
            ephemeral=NOTICE_EPHEMERAL,
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
                ephemeral=NOTICE_EPHEMERAL,
            )
            return
        except httpx.HTTPError:
            logger.exception("Force-saving Discord recipe import failed")
            await interaction.followup.send(
                "De recepten-API is momenteel niet bereikbaar.",
                ephemeral=NOTICE_EPHEMERAL,
            )
            return

        embed = build_recipe_import_embed(result)

        await interaction.edit_original_response(
            embed=embed,
            view=None,
        )
        await interaction.followup.send(
            "Het recept is opnieuw opgeslagen.",
            ephemeral=NOTICE_EPHEMERAL,
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
        if self.cancel_action is not None:
            await interaction.response.defer()
            try:
                await self.cancel_action()
            except httpx.HTTPError:
                logger.exception("Cancelling duplicate recipe import failed")
                await interaction.followup.send(
                    "De import kon niet bij de recepten-API worden geannuleerd.",
                    ephemeral=NOTICE_EPHEMERAL,
                )
                return

            await interaction.edit_original_response(
                content="Bestaand recept behouden.",
                embed=None,
                view=None,
            )
            self.stop()
            return

        await interaction.response.edit_message(
            content="Bestaand recept behouden.",
            embed=None,
            view=None,
        )

        self.stop()


class RecipeDeleteView(discord.ui.View):
    def __init__(
        self,
        *,
        api_client: RecipeApiClient,
        identifier: str,
        recipe_title: str,
        owner_id: int,
        timeout: float = 300,
    ) -> None:
        super().__init__(timeout=timeout)

        self.api_client = api_client
        self.identifier = identifier
        self.recipe_title = recipe_title
        self.owner_id = owner_id

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ) -> bool:
        if interaction.user.id == self.owner_id:
            return True

        await interaction.response.send_message(
            "Alleen de gebruiker die deze actie startte mag deze knoppen gebruiken.",
            ephemeral=NOTICE_EPHEMERAL,
        )
        return False

    @discord.ui.button(
        label="Definitief verwijderen",
        style=discord.ButtonStyle.danger,
    )
    async def confirm_delete(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await interaction.response.defer(
            thinking=True,
            ephemeral=NOTICE_EPHEMERAL,
        )

        self._disable_all_buttons()

        try:
            await self.api_client.delete_recipe(self.identifier)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                await interaction.followup.send(
                    "Dit recept bestaat inmiddels niet meer.",
                    ephemeral=NOTICE_EPHEMERAL,
                )
                self.stop()
                return

            await interaction.followup.send(
                (
                    "Het recept kon niet worden verwijderd. "
                    f"De API gaf status {exc.response.status_code}."
                ),
                ephemeral=NOTICE_EPHEMERAL,
            )
            return
        except httpx.HTTPError:
            logger.exception("Deleting Discord recipe failed")
            await interaction.followup.send(
                "De recepten-API is momenteel niet bereikbaar.",
                ephemeral=NOTICE_EPHEMERAL,
            )
            return

        logger.info(
            "Discord recipe deleted",
            extra={
                "recipe_identifier": self.identifier,
                "recipe_title": self.recipe_title,
                "discord_user_id": interaction.user.id,
                "discord_guild_id": interaction.guild_id,
                "discord_channel_id": interaction.channel_id,
            },
        )

        await interaction.edit_original_response(
            content=f"**{self.recipe_title}** is verwijderd.",
            embed=None,
            view=self,
        )

        self.stop()

    @discord.ui.button(
        label="Annuleren",
        style=discord.ButtonStyle.secondary,
    )
    async def cancel_delete(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        self._disable_all_buttons()

        logger.info(
            "Discord recipe deletion cancelled",
            extra={
                "recipe_identifier": self.identifier,
                "recipe_title": self.recipe_title,
                "discord_user_id": interaction.user.id,
                "discord_guild_id": interaction.guild_id,
                "discord_channel_id": interaction.channel_id,
            },
        )

        await interaction.response.edit_message(
            content=(f"Verwijderen van **{self.recipe_title}** is geannuleerd."),
            embed=None,
            view=self,
        )

        self.stop()

    def _disable_all_buttons(self) -> None:
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True


class DetectedUrlView(discord.ui.View):
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

    async def interaction_check(
        self,
        interaction: discord.Interaction,
    ) -> bool:
        if interaction.user.id == self.owner_id:
            return True

        await interaction.response.send_message(
            "Alleen de gebruiker die deze URL plaatste mag de preview starten.",
            ephemeral=NOTICE_EPHEMERAL,
        )
        return False

    @discord.ui.button(
        label="Preview maken",
        style=discord.ButtonStyle.primary,
    )
    async def preview_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        await interaction.response.defer(
            thinking=True,
            ephemeral=PREVIEW_EPHEMERAL,
        )

        try:
            result = await self.api_client.preview_website_recipe(self.source_url)
        except httpx.HTTPStatusError as exc:
            await interaction.followup.send(
                (
                    "De URL kon niet worden verwerkt. "
                    f"De API gaf status {exc.response.status_code}."
                ),
                ephemeral=NOTICE_EPHEMERAL,
            )
            return
        except httpx.HTTPError:
            logger.exception("Detected URL preview request failed")
            await interaction.followup.send(
                "De recepten-API is momenteel niet bereikbaar.",
                ephemeral=NOTICE_EPHEMERAL,
            )
            return

        async def save_website(
            force: bool,
        ) -> RecipeImportResponse:
            return await self.api_client.import_website_recipe(
                self.source_url,
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

        embed = build_recipe_import_embed(result)

        if result.status == "failed" and result.ai_enabled:
            import_view: discord.ui.View = ImportFailedView(
                api_client=self.api_client,
                retry_action=parse_with_ai,
                confirm_action=confirm_import,
                cancel_action=cancel_import,
                owner_id=self.owner_id,
            )
        else:
            import_view = RecipeImportView(
                api_client=self.api_client,
                import_action=(confirm_import if result.ai_enabled else save_website),
                owner_id=self.owner_id,
                ai_reparse_action=parse_with_ai if result.ai_enabled else None,
                confirm_action=confirm_import,
                cancel_action=cancel_import if result.ai_enabled else None,
            )

        message = await interaction.followup.send(
            embed=embed,
            view=import_view,
            ephemeral=PREVIEW_EPHEMERAL,
            wait=True,
        )

        import_view.message = message

        button.disabled = True

        if interaction.message is not None:
            await interaction.message.edit(view=self)

        self.stop()
