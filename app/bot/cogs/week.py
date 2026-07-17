import logging
from datetime import date, timedelta

import discord
import httpx
from discord import app_commands
from discord.ext import commands

from app.bot.api_client import RecipeApiClient
from app.bot.embeds import (
    build_generated_meal_plan_embed,
    build_meal_plan_embed,
)
from app.bot.meal_plan_errors import get_meal_plan_error_message
from app.bot.meal_plan_views import GeneratedMealPlanView

logger = logging.getLogger(__name__)

WEEKDAY_ALIASES = {
    "ma": 0,
    "mon": 0,
    "di": 1,
    "tue": 1,
    "wo": 2,
    "wed": 2,
    "do": 3,
    "thu": 3,
    "vr": 4,
    "fri": 4,
    "za": 5,
    "sat": 5,
    "zo": 6,
    "sun": 6,
}


def parse_weekdays(value: str | None) -> list[int]:
    if value is None or not value.strip():
        return []
    weekdays: set[int] = set()
    for raw_day in value.split(","):
        day = raw_day.strip().casefold()
        if day not in WEEKDAY_ALIASES:
            raise ValueError(f"Unknown weekday: {raw_day.strip()}")
        weekdays.add(WEEKDAY_ALIASES[day])
    return sorted(weekdays)


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

    MEAL_TYPE_CHOICES = [
        app_commands.Choice(
            name="Ontbijt",
            value="breakfast",
        ),
        app_commands.Choice(
            name="Lunch",
            value="lunch",
        ),
        app_commands.Choice(
            name="Avondeten",
            value="dinner",
        ),
    ]

    def __init__(
        self,
        api_client: RecipeApiClient,
    ) -> None:
        self.api_client = api_client

    async def _send_api_error(
        self,
        interaction: discord.Interaction,
        exc: httpx.HTTPError,
    ) -> None:
        logger.warning("Meal-plan API request failed", exc_info=exc)
        await interaction.followup.send(
            get_meal_plan_error_message(exc),
            ephemeral=True,
        )

    async def recipe_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str,
    ) -> list[app_commands.Choice[str]]:
        if not current.strip():
            return []

        results = await self.api_client.search_recipes(
            current,
            limit=25,
        )

        return [
            app_commands.Choice(
                name=recipe.title[:100],
                value=recipe.identifier,
            )
            for recipe in results[:25]
        ]

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
        except httpx.HTTPError as exc:
            await self._send_api_error(interaction, exc)
            return

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
    @app_commands.autocomplete(
        recept_id=recipe_autocomplete,
    )
    @app_commands.choices(
        maaltijd=MEAL_TYPE_CHOICES,
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
        except httpx.HTTPError as exc:
            await self._send_api_error(interaction, exc)
            return

        embed = build_meal_plan_embed(meal_plan)

        await interaction.followup.send(
            content=(f"`{recept_id}` is ingepland voor {parsed_date:%d-%m-%Y}."),
            embed=embed,
            ephemeral=True,
        )

    @week.command(
        name="wijzig",
        description="Wijzig een ingepland recept",
    )
    @app_commands.describe(
        entry_id="Het entry-ID uit /week toon",
        datum="Optionele nieuwe datum in formaat JJJJ-MM-DD",
        startdatum="Optionele startdatum in formaat JJJJ-MM-DD",
        porties="Optioneel nieuw aantal porties",
        maaltijd="Optioneel nieuw maaltijdtype",
        notitie="Optionele notitie; gebruik - om deze te wissen",
    )
    @app_commands.choices(maaltijd=MEAL_TYPE_CHOICES)
    async def update_entry(
        self,
        interaction: discord.Interaction,
        entry_id: int,
        datum: str | None = None,
        startdatum: str | None = None,
        porties: app_commands.Range[int, 1, 50] | None = None,
        maaltijd: str | None = None,
        notitie: str | None = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        if all(value is None for value in (datum, porties, maaltijd, notitie)):
            await interaction.followup.send(
                "Geef minstens één wijziging op.",
                ephemeral=True,
            )
            return

        try:
            parsed_date = date.fromisoformat(datum) if datum is not None else None
            if startdatum is None:
                current_plan = await self.api_client.get_current_meal_plan()
                parsed_start_date = current_plan.start_date
            else:
                parsed_start_date = date.fromisoformat(startdatum)

            meal_plan = await self.api_client.update_meal_plan_entry(
                start_date=parsed_start_date,
                entry_id=entry_id,
                planned_date=parsed_date,
                meal_type=maaltijd,
                servings=porties,
                notes=None if notitie == "-" else notitie,
                update_notes=notitie is not None,
            )
        except ValueError:
            await interaction.followup.send(
                "Een datum is ongeldig. Gebruik `JJJJ-MM-DD`.",
                ephemeral=True,
            )
            return
        except httpx.HTTPError as exc:
            await self._send_api_error(interaction, exc)
            return

        await interaction.followup.send(
            content=f"Planning-entry `{entry_id}` is gewijzigd.",
            embed=build_meal_plan_embed(meal_plan),
            ephemeral=True,
        )

    @week.command(
        name="verwijder",
        description="Verwijder een ingepland recept",
    )
    @app_commands.describe(
        entry_id="Het entry-ID uit /week toon",
        startdatum="Optionele startdatum in formaat JJJJ-MM-DD",
    )
    async def remove_entry(
        self,
        interaction: discord.Interaction,
        entry_id: int,
        startdatum: str | None = None,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        try:
            if startdatum is None:
                current_plan = await self.api_client.get_current_meal_plan()
                parsed_start_date = current_plan.start_date
            else:
                parsed_start_date = date.fromisoformat(startdatum)

            meal_plan = await self.api_client.remove_meal_plan_entry(
                start_date=parsed_start_date,
                entry_id=entry_id,
            )
        except ValueError:
            await interaction.followup.send(
                "De startdatum is ongeldig. Gebruik `JJJJ-MM-DD`.",
                ephemeral=True,
            )
            return
        except httpx.HTTPError as exc:
            await self._send_api_error(interaction, exc)
            return

        await interaction.followup.send(
            content=f"Planning-entry `{entry_id}` is verwijderd.",
            embed=build_meal_plan_embed(meal_plan),
            ephemeral=True,
        )

    @week.command(
        name="genereer",
        description="Maak automatisch een voorstel voor de weekplanning",
    )
    @app_commands.describe(
        startdatum="Optionele startdatum in formaat JJJJ-MM-DD",
        porties="Aantal personen",
        max_werktijd="Maximale bereidingstijd op werkdagen",
        vegetarische_dagen="Kommalijst, bijvoorbeeld do,zo",
        recente_recepten_vermijden="Aantal dagen zonder recente recepten",
    )
    @app_commands.checks.cooldown(
        2,
        60.0,
        key=lambda interaction: interaction.user.id,
    )
    async def generate_week(
        self,
        interaction: discord.Interaction,
        startdatum: str | None = None,
        porties: app_commands.Range[int, 1, 50] = 2,
        max_werktijd: app_commands.Range[int, 0, 600] | None = None,
        vegetarische_dagen: str | None = None,
        recente_recepten_vermijden: app_commands.Range[int, 0, 3650] = 21,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            parsed_start_date = (
                date.fromisoformat(startdatum) if startdatum is not None else None
            )
            parsed_vegetarian_days = parse_weekdays(vegetarische_dagen)
        except ValueError:
            await interaction.followup.send(
                (
                    "De datum of vegetarische dagen zijn ongeldig. Gebruik "
                    "`JJJJ-MM-DD` en dagen zoals `ma,di,wo,do,vr,za,zo`."
                ),
                ephemeral=True,
            )
            return

        try:
            result = await self.api_client.generate_meal_plan(
                start_date=parsed_start_date,
                servings=porties,
                max_preparation_time_weekday=max_werktijd,
                vegetarian_days=parsed_vegetarian_days,
                avoid_recent_days=recente_recepten_vermijden,
                created_by=str(interaction.user.id),
            )
        except httpx.HTTPError as exc:
            await self._send_api_error(interaction, exc)
            return

        view = GeneratedMealPlanView(
            api_client=self.api_client,
            result=result,
            owner_id=interaction.user.id,
        )
        await interaction.followup.send(
            embed=build_generated_meal_plan_embed(result),
            view=view,
            ephemeral=True,
        )

    @week.command(
        name="vervang",
        description="Kies opnieuw voor één gegenereerde planning-entry",
    )
    @app_commands.describe(
        voorstel_id="Het planning-ID van het voorstel",
        entry_id="Het entry-ID uit het voorstel",
    )
    async def reroll_entry(
        self,
        interaction: discord.Interaction,
        voorstel_id: int,
        entry_id: int,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        try:
            result = await self.api_client.reroll_meal_plan_entry(
                plan_id=voorstel_id,
                entry_id=entry_id,
            )
        except httpx.HTTPError as exc:
            await self._send_api_error(interaction, exc)
            return
        view = GeneratedMealPlanView(
            api_client=self.api_client,
            result=result,
            owner_id=interaction.user.id,
        )
        await interaction.followup.send(
            content=f"Planning-entry `{entry_id}` heeft een nieuw recept.",
            embed=build_generated_meal_plan_embed(result),
            view=view,
            ephemeral=True,
        )
