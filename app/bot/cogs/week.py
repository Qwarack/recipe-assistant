from datetime import date, timedelta

import discord
import httpx
from discord import app_commands
from discord.ext import commands

from app.bot.api_client import RecipeApiClient
from app.bot.embeds import build_meal_plan_embed


def get_planning_start_date(
    target_date: date,
) -> date:
    days_since_wednesday = (target_date.weekday() - 2) % 7

    return target_date - timedelta(days=days_since_wednesday)


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

    @week.command(
        name="plan",
        description="Plan een recept in voor een bepaalde dag",
    )
    @app_commands.describe(
        recept_id="De identifier van het recept",
        datum="Datum in formaat JJJJ-MM-DD",
        startdatum=("Optioneel; standaard wordt de vorige woensdag gebruikt"),
        porties="Aantal porties",
        maaltijd="Bijvoorbeeld dinner, lunch of breakfast",
        notitie="Optionele notitie",
    )
    async def plan_recipe(
        self,
        interaction: discord.Interaction,
        recept_id: str,
        datum: str,
        startdatum: str | None = None,
        porties: app_commands.Range[int, 1, 50] = 2,
        maaltijd: str = "dinner",
        notitie: str | None = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        try:
            parsed_date = date.fromisoformat(datum)

            if startdatum is None:
                parsed_start_date = get_planning_start_date(parsed_date)
            else:
                parsed_start_date = date.fromisoformat(startdatum)

        except ValueError:
            await interaction.followup.send(
                (
                    "Een van de datums is ongeldig. "
                    "Gebruik `JJJJ-MM-DD`, bijvoorbeeld "
                    "`2026-07-15`."
                ),
                ephemeral=True,
            )
            return

        try:
            meal_plan = await self.api_client.add_meal_plan_entry(
                start_date=parsed_start_date,
                planned_date=parsed_date,
                recipe_identifier=recept_id,
                meal_type=maaltijd,
                servings=porties,
                notes=notitie,
            )
        except httpx.HTTPStatusError as exc:
            status_code = exc.response.status_code

            try:
                detail = exc.response.json().get(
                    "detail",
                    "Onbekende fout",
                )
            except ValueError:
                detail = "Onbekende fout"

            if status_code == 404:
                message = f"Het recept `{recept_id}` is niet gevonden."
            elif status_code == 409:
                message = f"Het recept kon niet worden ingepland: {detail}"
            else:
                raise

            await interaction.followup.send(
                message,
                ephemeral=True,
            )
            return

        embed = build_meal_plan_embed(meal_plan)

        await interaction.followup.send(
            content=(f"`{recept_id}` is ingepland voor {parsed_date:%d-%m-%Y}."),
            embed=embed,
            ephemeral=True,
        )
