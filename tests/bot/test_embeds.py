from app.bot.api_client import (
    RecipeDetail,
    RecipeImportResponse,
    RecipePreview,
)
from app.bot.embeds import build_recipe_detail_embed, build_recipe_import_embed


def test_builds_recipe_import_embed() -> None:
    result = RecipeImportResponse(
        import_id="abc123",
        status="success",
        destination="/data/recipes/pasta.md",
        recipe=RecipePreview(
            title="Pasta Carbonara",
            servings=4,
            prep_time_minutes=10,
            cook_time_minutes=20,
            total_time_minutes=30,
            ingredient_count=6,
            instruction_count=5,
            source_url="https://example.com/carbonara",
        ),
        warnings=[],
    )

    embed = build_recipe_import_embed(result)

    assert embed.title == "Pasta Carbonara"
    assert embed.url == "https://example.com/carbonara"
    assert "success" in (embed.description or "")
    assert len(embed.fields) == 4


def test_embed_includes_warnings() -> None:
    result = RecipeImportResponse(
        import_id="abc123",
        status="partial",
        destination=None,
        recipe=RecipePreview(
            title="Pasta Carbonara",
            servings=None,
            prep_time_minutes=None,
            cook_time_minutes=None,
            total_time_minutes=None,
            ingredient_count=4,
            instruction_count=3,
            source_url=None,
        ),
        warnings=[
            {
                "code": "duplicate_title",
                "message": "A similar recipe already exists.",
            }
        ],
    )

    embed = build_recipe_import_embed(result)

    warning_field = next(
        field for field in embed.fields if field.name == "Waarschuwingen"
    )

    assert "similar recipe" in warning_field.value


def test_builds_recipe_detail_embed() -> None:
    recipe = RecipeDetail(
        identifier="pasta-carbonara",
        title="Pasta Carbonara",
        ingredients=[
            "400 g spaghetti",
            "4 eieren",
        ],
        instructions=[
            "Kook de spaghetti.",
            "Meng de eieren.",
        ],
        servings=4,
        prep_time_minutes=10,
        cook_time_minutes=20,
        total_time_minutes=30,
        source_url="https://example.com/carbonara",
        tags=["pasta", "italian"],
        meal_types=["dinner"],
    )

    embed = build_recipe_detail_embed(recipe)

    assert embed.title == "Pasta Carbonara"
    assert embed.url == "https://example.com/carbonara"
    assert "Porties" in (embed.description or "")
    assert len(embed.fields) == 4
    assert embed.fields[0].name == "Ingrediënten"
    assert "400 g spaghetti" in embed.fields[0].value
    assert embed.footer.text == ("Recept-ID: pasta-carbonara")
