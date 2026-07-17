from datetime import date

import discord
import httpx
from discord import app_commands
from discord.ext import commands

from app.bot.api_client import RecipeApiClient
from app.bot.embeds import build_meal_plan_embed


class WeekCommands(commands.Cog):
    week = app_commands.Group(
        name="week",
        description="Beheer de weekplanning",
    )

    def __init__(
        self,
        api_client: RecipeApiClient,
    ) -> None:
        self.api_client = api_client

    @week.command(
        name="toon",
        description="Toon de huidige of een specifieke weekplanning",
    )
    @app_commands.describe(
        startdatum="Optionele startdatum in formaat JJJJ-MM-DD",
    )
    async def show_week(
        self,
        interaction: discord.Interaction,
        startdatum: str | None = None,
    ) -> None:
        await interaction.response.defer()

        try:
            if startdatum is None:
                meal_plan = await self.api_client.get_current_meal_plan()
            else:
                parsed_start_date = date.fromisoformat(startdatum)
                meal_plan = await self.api_client.get_meal_plan(parsed_start_date)
        except ValueError:
            await interaction.followup.send(
                (
                    "De startdatum is ongeldig. "
                    "Gebruik het formaat `JJJJ-MM-DD`, "
                    "bijvoorbeeld `2026-07-15`."
                ),
                ephemeral=True,
            )
            return
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 404:
                await interaction.followup.send(
                    "Er is geen weekplanning gevonden.",
                    ephemeral=True,
                )
                return

            raise

        embed = build_meal_plan_embed(meal_plan)

        await interaction.followup.send(embed=embed)
