import logging
from collections.abc import Awaitable, Callable

import discord
import httpx

from app.bot.api_client import RecipeApiClient, RecipeImportResponse
from app.bot.constants import NOTICE_EPHEMERAL, PREVIEW_EPHEMERAL
from app.bot.embeds import build_recipe_import_embed, recipe_field_label

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
        ai_enrichment_action: AIAction | None = None,
        openai_fallback_action: AIAction | None = None,
        openai_fallback_available: bool = False,
        enrichable_fields: list[str] | None = None,
        confidence_action: str | None = None,
        confirm_action: ImportAction | None = None,
        cancel_action: CancelAction | None = None,
        ai_generated: bool = False,
        timeout: float = 300,
    ) -> None:
        super().__init__(timeout=timeout)

        self.api_client = api_client
        self.import_action = import_action
        self.ai_reparse_action = ai_reparse_action
        self.ai_enrichment_action = ai_enrichment_action
        self.openai_fallback_action = openai_fallback_action
        self.enrichable_fields = enrichable_fields or []
        self.confidence_action = confidence_action
        self.confirm_action = confirm_action or import_action
        self.cancel_action = cancel_action
        self.owner_id = owner_id
        self.message: discord.InteractionMessage | None = None

        if ai_reparse_action is None:
            self.remove_item(self.ai_reparse_button)
        elif ai_generated:
            self.ai_reparse_button.label = "Nogmaals volledig met AI"

        if ai_enrichment_action is None or not self.enrichable_fields:
            self.remove_item(self.ai_enrichment_button)
        if openai_fallback_action is None or not openai_fallback_available:
            self.remove_item(self.openai_fallback_button)
        if confidence_action == "try_local_ai":
            self.ai_reparse_button.label = "Aanbevolen: controleer met Qwen3.5"
        elif confidence_action == "retry_local_ai":
            self.ai_reparse_button.label = "Aanbevolen: Qwen3.5 opnieuw"
        elif confidence_action == "manual_review":
            self.save_button.label = "Opslaan na handmatige controle"

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
        label="Hele recept opnieuw met AI",
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
            self._reveal_openai_fallback()
            await interaction.edit_original_response(view=self)
            await interaction.followup.send(
                _http_error_message(
                    exc,
                    fallback=(
                        "Qwen3.5 kon dit recept niet verwerken. "
                        "Je kunt het opnieuw proberen."
                    ),
                ),
                ephemeral=NOTICE_EPHEMERAL,
            )
            await self._send_openai_fallback_notice(interaction)
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
            ai_enrichment_action=self.ai_enrichment_action,
            openai_fallback_action=self.openai_fallback_action,
            openai_fallback_available=result.openai_fallback_available,
            enrichable_fields=(
                result.metadata.enrichable_fields if result.metadata is not None else []
            ),
            confidence_action=(
                result.metadata.confidence_action
                if result.metadata is not None
                else None
            ),
            confirm_action=self.confirm_action,
            cancel_action=self.cancel_action,
            ai_generated=True,
        )
        replacement.message = self.message

        await interaction.edit_original_response(
            embed=build_recipe_import_embed(result),
            view=replacement,
        )
        await interaction.followup.send(
            (
                "Qwen3.5 heeft een nieuwe volledige preview gemaakt. "
                "Controleer het hele recept voordat je het opslaat."
            ),
            ephemeral=NOTICE_EPHEMERAL,
        )
        self.stop()

    @discord.ui.button(
        label="Ontbrekende metadata aanvullen",
        style=discord.ButtonStyle.secondary,
    )
    async def ai_enrichment_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        if self.ai_enrichment_action is None:
            return

        requested_fields = self.enrichable_fields.copy()
        await interaction.response.defer(thinking=True)
        self._disable_all_buttons()

        try:
            result = await self.ai_enrichment_action()
        except httpx.HTTPStatusError as exc:
            self._enable_all_buttons()
            await interaction.edit_original_response(view=self)
            await interaction.followup.send(
                _http_error_message(
                    exc,
                    fallback=(
                        "Qwen3.5 kon de ontbrekende metadata niet aanvullen. "
                        "Het oorspronkelijke recept is niet gewijzigd."
                    ),
                ),
                ephemeral=NOTICE_EPHEMERAL,
            )
            return
        except httpx.HTTPError:
            self._enable_all_buttons()
            await interaction.edit_original_response(view=self)
            logger.exception("AI recipe metadata enrichment request failed")
            await interaction.followup.send(
                (
                    "De recepten-API is momenteel niet bereikbaar. "
                    "Het oorspronkelijke recept is niet gewijzigd."
                ),
                ephemeral=NOTICE_EPHEMERAL,
            )
            return

        remaining_fields = (
            result.metadata.enrichable_fields if result.metadata is not None else []
        )
        completed_fields = [
            field_name
            for field_name in requested_fields
            if field_name not in remaining_fields
        ]
        replacement = RecipeImportView(
            api_client=self.api_client,
            import_action=self.confirm_action,
            owner_id=self.owner_id,
            ai_reparse_action=self.ai_reparse_action,
            ai_enrichment_action=self.ai_enrichment_action,
            openai_fallback_action=self.openai_fallback_action,
            openai_fallback_available=result.openai_fallback_available,
            enrichable_fields=remaining_fields,
            confidence_action=(
                result.metadata.confidence_action
                if result.metadata is not None
                else None
            ),
            confirm_action=self.confirm_action,
            cancel_action=self.cancel_action,
            ai_generated=True,
        )
        replacement.message = self.message

        await interaction.edit_original_response(
            embed=build_recipe_import_embed(result),
            view=replacement,
        )
        if completed_fields:
            completed = ", ".join(
                recipe_field_label(field_name) for field_name in completed_fields
            )
            message = (
                f"Qwen3.5 heeft alleen deze lege metadata aangevuld: **{completed}**. "
                "Bestaande receptgegevens zijn behouden. Controleer de schattingen "
                "voordat je opslaat."
            )
        else:
            message = (
                "Qwen3.5 kon geen ontbrekende metadata verantwoord aanvullen. "
                "Het recept is inhoudelijk niet gewijzigd."
            )
        await interaction.followup.send(message, ephemeral=NOTICE_EPHEMERAL)
        self.stop()

    @discord.ui.button(
        label="Laatste poging met ChatGPT (API)",
        style=discord.ButtonStyle.danger,
    )
    async def openai_fallback_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        if self.openai_fallback_action is None:
            return

        await interaction.response.defer(thinking=True)
        self._disable_all_buttons()

        try:
            result = await self.openai_fallback_action()
        except httpx.HTTPStatusError as exc:
            self._enable_all_buttons()
            await interaction.edit_original_response(view=self)
            await interaction.followup.send(
                _http_error_message(
                    exc,
                    fallback=(
                        "ChatGPT kon de oorspronkelijke receptbron niet verwerken. "
                        "De bestaande preview is niet gewijzigd."
                    ),
                ),
                ephemeral=NOTICE_EPHEMERAL,
            )
            return
        except httpx.HTTPError:
            self._enable_all_buttons()
            await interaction.edit_original_response(view=self)
            logger.exception("OpenAI recipe fallback request failed")
            await interaction.followup.send(
                (
                    "De recepten-API is momenteel niet bereikbaar. "
                    "De bestaande preview is niet gewijzigd."
                ),
                ephemeral=NOTICE_EPHEMERAL,
            )
            return

        replacement = RecipeImportView(
            api_client=self.api_client,
            import_action=self.confirm_action,
            owner_id=self.owner_id,
            ai_reparse_action=self.ai_reparse_action,
            ai_enrichment_action=self.ai_enrichment_action,
            openai_fallback_action=self.openai_fallback_action,
            openai_fallback_available=result.openai_fallback_available,
            enrichable_fields=(
                result.metadata.enrichable_fields if result.metadata is not None else []
            ),
            confidence_action=(
                result.metadata.confidence_action
                if result.metadata is not None
                else None
            ),
            confirm_action=self.confirm_action,
            cancel_action=self.cancel_action,
            ai_generated=True,
        )
        replacement.message = self.message
        await interaction.edit_original_response(
            embed=build_recipe_import_embed(result),
            view=replacement,
        )
        await interaction.followup.send(
            (
                "ChatGPT heeft de **oorspronkelijke receptbron** verwerkt. "
                "Controleer de volledige nieuwe preview voordat je opslaat."
            ),
            ephemeral=NOTICE_EPHEMERAL,
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

    def _reveal_openai_fallback(self) -> None:
        if (
            self.openai_fallback_action is not None
            and self.openai_fallback_button not in self.children
        ):
            self.add_item(self.openai_fallback_button)

    async def _send_openai_fallback_notice(
        self,
        interaction: discord.Interaction,
    ) -> None:
        if self.openai_fallback_button not in self.children:
            return
        await interaction.followup.send(
            (
                "Qwen3.5 is geprobeerd en mislukt; de bestaande preview is "
                "behouden. Als laatste optie kun je **Laatste poging met ChatGPT "
                "(API)** kiezen. Alleen dan wordt de oorspronkelijke receptbron "
                "naar OpenAI gestuurd en kunnen API-kosten ontstaan."
            ),
            ephemeral=NOTICE_EPHEMERAL,
        )


class ImportFailedView(discord.ui.View):
    def __init__(
        self,
        *,
        api_client: RecipeApiClient,
        retry_action: AIAction,
        enrichment_action: AIAction,
        openai_fallback_action: AIAction | None = None,
        openai_fallback_available: bool = False,
        confirm_action: ImportAction,
        cancel_action: CancelAction,
        owner_id: int,
        timeout: float = 300,
    ) -> None:
        super().__init__(timeout=timeout)
        self.api_client = api_client
        self.retry_action = retry_action
        self.enrichment_action = enrichment_action
        self.openai_fallback_action = openai_fallback_action
        self.confirm_action = confirm_action
        self.cancel_action = cancel_action
        self.owner_id = owner_id
        self.message: discord.InteractionMessage | None = None

        if openai_fallback_action is None or not openai_fallback_available:
            self.remove_item(self.openai_fallback_button)

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
        label="Recept herstellen met AI",
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
            self._reveal_openai_fallback()
            await interaction.edit_original_response(view=self)
            await interaction.followup.send(
                _http_error_message(
                    exc,
                    fallback=(
                        "Qwen3.5 kon dit recept niet verwerken. "
                        "Je kunt het opnieuw proberen."
                    ),
                ),
                ephemeral=NOTICE_EPHEMERAL,
            )
            await self._send_openai_fallback_notice(interaction)
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
            ai_enrichment_action=self.enrichment_action,
            openai_fallback_action=self.openai_fallback_action,
            openai_fallback_available=result.openai_fallback_available,
            enrichable_fields=(
                result.metadata.enrichable_fields if result.metadata is not None else []
            ),
            confidence_action=(
                result.metadata.confidence_action
                if result.metadata is not None
                else None
            ),
            confirm_action=self.confirm_action,
            cancel_action=self.cancel_action,
            ai_generated=True,
        )
        replacement.message = self.message
        await interaction.edit_original_response(
            embed=build_recipe_import_embed(result),
            view=replacement,
        )
        await interaction.followup.send(
            (
                "Qwen3.5 heeft een receptpreview gemaakt. Controleer het recept "
                "en vul ontbrekende metadata desgewenst apart aan."
            ),
            ephemeral=NOTICE_EPHEMERAL,
        )
        self.stop()

    @discord.ui.button(
        label="Laatste poging met ChatGPT (API)",
        style=discord.ButtonStyle.danger,
    )
    async def openai_fallback_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        if self.openai_fallback_action is None:
            return

        await interaction.response.defer(thinking=True)
        self._set_disabled(True)

        try:
            result = await self.openai_fallback_action()
        except httpx.HTTPStatusError as exc:
            self._set_disabled(False)
            await interaction.edit_original_response(view=self)
            await interaction.followup.send(
                _http_error_message(
                    exc,
                    fallback=(
                        "ChatGPT kon de oorspronkelijke receptbron niet verwerken. "
                        "Er is nog niets opgeslagen."
                    ),
                ),
                ephemeral=NOTICE_EPHEMERAL,
            )
            return
        except httpx.HTTPError:
            self._set_disabled(False)
            await interaction.edit_original_response(view=self)
            logger.exception("OpenAI failed-import fallback request failed")
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
            ai_enrichment_action=self.enrichment_action,
            openai_fallback_action=self.openai_fallback_action,
            openai_fallback_available=result.openai_fallback_available,
            enrichable_fields=(
                result.metadata.enrichable_fields if result.metadata is not None else []
            ),
            confidence_action=(
                result.metadata.confidence_action
                if result.metadata is not None
                else None
            ),
            confirm_action=self.confirm_action,
            cancel_action=self.cancel_action,
            ai_generated=True,
        )
        replacement.message = self.message
        await interaction.edit_original_response(
            embed=build_recipe_import_embed(result),
            view=replacement,
        )
        await interaction.followup.send(
            (
                "ChatGPT heeft de **oorspronkelijke receptbron** verwerkt. "
                "Controleer de volledige preview voordat je opslaat."
            ),
            ephemeral=NOTICE_EPHEMERAL,
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

    def _reveal_openai_fallback(self) -> None:
        if (
            self.openai_fallback_action is not None
            and self.openai_fallback_button not in self.children
        ):
            self.add_item(self.openai_fallback_button)

    async def _send_openai_fallback_notice(
        self,
        interaction: discord.Interaction,
    ) -> None:
        if self.openai_fallback_button not in self.children:
            return
        await interaction.followup.send(
            (
                "Qwen3.5 is geprobeerd en mislukt. Als laatste optie kun je "
                "**Laatste poging met ChatGPT (API)** kiezen. Alleen na die klik "
                "wordt de oorspronkelijke receptbron naar OpenAI gestuurd en "
                "kunnen API-kosten ontstaan."
            ),
            ephemeral=NOTICE_EPHEMERAL,
        )


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

        async def enrich_metadata_with_ai() -> RecipeImportResponse:
            return await self.api_client.enrich_import_metadata_with_ai(
                result.import_id,
                discord_user_id=self.owner_id,
            )

        async def parse_with_openai() -> RecipeImportResponse:
            return await self.api_client.parse_import_with_openai(
                result.import_id,
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
                enrichment_action=enrich_metadata_with_ai,
                openai_fallback_action=(
                    parse_with_openai if result.openai_enabled else None
                ),
                openai_fallback_available=result.openai_fallback_available,
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
                ai_enrichment_action=(
                    enrich_metadata_with_ai if result.ai_enabled else None
                ),
                openai_fallback_action=(
                    parse_with_openai if result.openai_enabled else None
                ),
                openai_fallback_available=result.openai_fallback_available,
                enrichable_fields=(
                    result.metadata.enrichable_fields
                    if result.metadata is not None
                    else []
                ),
                confidence_action=(
                    result.metadata.confidence_action
                    if result.metadata is not None
                    else None
                ),
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
