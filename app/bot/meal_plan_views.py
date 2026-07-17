import logging
import secrets
import time

import discord
import httpx

from app.bot.api_client import GeneratedMealPlan, RecipeApiClient
from app.bot.embeds import build_generated_meal_plan_embed
from app.bot.meal_plan_errors import get_meal_plan_error_message

logger = logging.getLogger(__name__)


class GeneratedMealPlanView(discord.ui.View):
    def __init__(
        self,
        *,
        api_client: RecipeApiClient,
        result: GeneratedMealPlan,
        owner_id: int,
        timeout: float = 300,
    ) -> None:
        super().__init__(timeout=timeout)
        self.api_client = api_client
        self.result = result
        self.owner_id = owner_id
        self.busy = False
        self.last_regenerated_at: float | None = None
        self.regenerate_cooldown_seconds = 5.0

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.owner_id and not self.busy:
            return True
        message = (
            "Dit voorstel wordt al verwerkt."
            if self.busy
            else (
                "Alleen de gebruiker die dit voorstel maakte mag deze knoppen "
                "gebruiken."
            )
        )
        await interaction.response.send_message(message, ephemeral=True)
        return False

    @discord.ui.button(label="Accepteren", style=discord.ButtonStyle.success)
    async def accept_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        del button
        await interaction.response.defer()
        self.busy = True
        try:
            plan = await self.api_client.activate_meal_plan(
                plan_id=self.result.plan.id,
                activated_by=str(self.owner_id),
            )
        except httpx.HTTPError as exc:
            await self._send_error(interaction, exc)
            return

        self.result = GeneratedMealPlan(
            plan=plan,
            unfilled_slots=[],
            selection_explanations=[],
            generation_seed=self.result.generation_seed,
        )
        self._disable_all()
        await interaction.edit_original_response(
            content="De weekplanning is geactiveerd.",
            embed=build_generated_meal_plan_embed(self.result),
            view=self,
        )
        self.stop()

    @discord.ui.button(
        label="Opnieuw genereren",
        style=discord.ButtonStyle.primary,
    )
    async def regenerate_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        del button
        now = time.monotonic()
        if (
            self.last_regenerated_at is not None
            and now - self.last_regenerated_at < self.regenerate_cooldown_seconds
        ):
            await interaction.response.send_message(
                "Wacht enkele seconden voordat je opnieuw genereert.",
                ephemeral=True,
            )
            return
        self.last_regenerated_at = now
        await interaction.response.defer()
        self.busy = True
        seed = secrets.randbits(63)
        try:
            result = await self.api_client.regenerate_meal_plan(
                plan_id=self.result.plan.id,
                random_seed=seed,
            )
        except httpx.HTTPError as exc:
            await self._send_error(interaction, exc)
            return
        self.result = result
        self.busy = False
        await interaction.edit_original_response(
            content="Er is een nieuw voorstel gemaakt.",
            embed=build_generated_meal_plan_embed(result),
            view=self,
        )

    @discord.ui.button(label="Annuleren", style=discord.ButtonStyle.danger)
    async def cancel_button(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ) -> None:
        del button
        await interaction.response.defer()
        self.busy = True
        try:
            await self.api_client.cancel_meal_plan_draft(plan_id=self.result.plan.id)
        except httpx.HTTPError as exc:
            await self._send_error(interaction, exc)
            return
        self._disable_all()
        await interaction.edit_original_response(
            content="Het weekvoorstel is geannuleerd.",
            embed=build_generated_meal_plan_embed(self.result),
            view=self,
        )
        self.stop()

    async def _send_error(
        self,
        interaction: discord.Interaction,
        exc: httpx.HTTPError,
    ) -> None:
        logger.warning("Generated meal-plan action failed", exc_info=exc)
        self.busy = False
        await interaction.followup.send(
            get_meal_plan_error_message(exc),
            ephemeral=True,
        )

    def _disable_all(self) -> None:
        self.busy = True
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                child.disabled = True
