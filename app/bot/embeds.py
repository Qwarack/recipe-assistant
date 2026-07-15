import discord

from app.bot.api_client import RecipeImportResponse


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
