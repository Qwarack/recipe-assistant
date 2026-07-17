import discord

from app.bot.api_client import MealPlan, RecipeDetail, RecipeImportResponse
from app.bot.text_utils import split_text

DUTCH_WEEKDAYS = {
    0: "Maandag",
    1: "Dinsdag",
    2: "Woensdag",
    3: "Donderdag",
    4: "Vrijdag",
    5: "Zaterdag",
    6: "Zondag",
}


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return f"{value[: limit - 1]}…"


def build_recipe_import_embed(
    result: RecipeImportResponse,
) -> discord.Embed:
    if result.recipe is None:
        return discord.Embed(
            title="Receptimport voltooid",
            description=(
                f"Status: **{result.status}**\nImport-ID: `{result.import_id}`"
            ),
        )

    recipe = result.recipe

    embed = discord.Embed(
        title=recipe.title,
        url=recipe.source_url,
        description=(
            f"Importstatus: **{result.status}**\nImport-ID: `{result.import_id}`"
        ),
    )

    if recipe.servings is not None:
        embed.add_field(
            name="Porties",
            value=str(recipe.servings),
            inline=True,
        )

    if recipe.total_time_minutes is not None:
        embed.add_field(
            name="Totale tijd",
            value=f"{recipe.total_time_minutes} min",
            inline=True,
        )
    else:
        if recipe.prep_time_minutes is not None:
            embed.add_field(
                name="Voorbereiding",
                value=f"{recipe.prep_time_minutes} min",
                inline=True,
            )

        if recipe.cook_time_minutes is not None:
            embed.add_field(
                name="Bereiding",
                value=f"{recipe.cook_time_minutes} min",
                inline=True,
            )

    embed.add_field(
        name="Ingrediënten",
        value=str(recipe.ingredient_count),
        inline=True,
    )
    embed.add_field(
        name="Stappen",
        value=str(recipe.instruction_count),
        inline=True,
    )

    if result.warnings:
        warning_lines = [f"• {warning['message']}" for warning in result.warnings]

        warning_chunks = split_text(warning_lines)

        for index, chunk in enumerate(
            warning_chunks,
            start=1,
        ):
            field_name = "Waarschuwingen" if index == 1 else f"Waarschuwingen ({index})"

            embed.add_field(
                name=field_name,
                value=chunk,
                inline=False,
            )

    if result.destination is not None:
        embed.set_footer(text=f"Opgeslagen als: {result.destination}")

    return embed


def build_recipe_detail_embed(
    recipe: RecipeDetail,
) -> discord.Embed:
    embed = discord.Embed(
        title=recipe.title,
        url=recipe.source_url,
    )

    summary_parts: list[str] = []

    if recipe.servings is not None:
        summary_parts.append(f"Porties: **{recipe.servings}**")

    if recipe.total_time_minutes is not None:
        summary_parts.append(f"Totale tijd: **{recipe.total_time_minutes} min**")
    else:
        if recipe.prep_time_minutes is not None:
            summary_parts.append(f"Voorbereiding: **{recipe.prep_time_minutes} min**")

        if recipe.cook_time_minutes is not None:
            summary_parts.append(f"Bereiding: **{recipe.cook_time_minutes} min**")

    if summary_parts:
        embed.description = "\n".join(summary_parts)

    ingredient_lines = [f"• {ingredient}" for ingredient in recipe.ingredients]

    ingredient_chunks = split_text(ingredient_lines)

    if not ingredient_chunks:
        embed.add_field(
            name="Ingrediënten",
            value="Geen ingrediënten gevonden.",
            inline=False,
        )
    else:
        for index, chunk in enumerate(
            ingredient_chunks,
            start=1,
        ):
            field_name = "Ingrediënten" if index == 1 else f"Ingrediënten ({index})"

            embed.add_field(
                name=field_name,
                value=chunk,
                inline=False,
            )

    instruction_lines = [
        f"{index}. {instruction}"
        for index, instruction in enumerate(
            recipe.instructions,
            start=1,
        )
    ]

    instruction_chunks = split_text(instruction_lines)

    if not instruction_chunks:
        embed.add_field(
            name="Bereiding",
            value="Geen stappen gevonden.",
            inline=False,
        )
    else:
        for index, chunk in enumerate(
            instruction_chunks,
            start=1,
        ):
            field_name = "Bereiding" if index == 1 else f"Bereiding ({index})"

            embed.add_field(
                name=field_name,
                value=chunk,
                inline=False,
            )

    if recipe.tags:
        embed.add_field(
            name="Tags",
            value=", ".join(recipe.tags)[:1024],
            inline=False,
        )

    if recipe.meal_types:
        embed.add_field(
            name="Maaltijdtypes",
            value=", ".join(recipe.meal_types)[:1024],
            inline=False,
        )

    embed.set_footer(text=f"Recept-ID: {recipe.identifier}")

    return embed


def build_meal_plan_embed(
    meal_plan: MealPlan,
) -> discord.Embed:
    title = meal_plan.name or "Weekplanning"

    embed = discord.Embed(
        title=title,
        description=(
            f"Periode: **{meal_plan.start_date:%d-%m-%Y}** "
            f"t/m **{meal_plan.end_date:%d-%m-%Y}**"
        ),
    )

    if not meal_plan.entries:
        embed.add_field(
            name="Planning",
            value="Er zijn nog geen recepten ingepland.",
            inline=False,
        )
        embed.set_footer(text=f"Planning-ID: {meal_plan.id}")
        return embed

    sorted_entries = sorted(
        meal_plan.entries,
        key=lambda entry: (
            entry.planned_date,
            entry.meal_type,
        ),
    )

    for entry in sorted_entries[:25]:
        weekday = DUTCH_WEEKDAYS[entry.planned_date.weekday()]
        field_name = f"{weekday} {entry.planned_date:%d-%m} · {entry.meal_type}"

        field_value = (
            f"**{_truncate(entry.recipe_title, 48)}**\n"
            f"Porties: {entry.servings}\n"
            f"Notitie: {_truncate(entry.notes or '—', 60)}\n"
            f"Entry-ID: `{entry.id}`\n"
            f"Recept-ID: `{_truncate(entry.recipe_identifier, 64)}`"
        )

        embed.add_field(
            name=_truncate(field_name, 256),
            value=_truncate(field_value, 240),
            inline=False,
        )

    embed.set_footer(text=f"Planning-ID: {meal_plan.id}")

    return embed
