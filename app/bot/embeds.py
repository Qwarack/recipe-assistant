import discord

from app.bot.api_client import RecipeDetail, RecipeImportResponse


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

        embed.add_field(
            name="Waarschuwingen",
            value="\n".join(warning_lines)[:1024],
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

    ingredient_text = "\n".join(f"• {ingredient}" for ingredient in recipe.ingredients)

    embed.add_field(
        name="Ingrediënten",
        value=ingredient_text[:1024] or "Geen ingrediënten gevonden.",
        inline=False,
    )

    instruction_text = "\n".join(
        f"{index}. {instruction}"
        for index, instruction in enumerate(
            recipe.instructions,
            start=1,
        )
    )

    embed.add_field(
        name="Bereiding",
        value=instruction_text[:1024] or "Geen stappen gevonden.",
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
