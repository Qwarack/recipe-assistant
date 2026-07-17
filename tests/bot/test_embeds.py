from datetime import date

from app.bot.api_client import (
    MealPlan,
    MealPlanEntry,
    RecipeDetail,
    RecipeImportResponse,
    RecipePreview,
)
from app.bot.embeds import (
    build_meal_plan_embed,
    build_recipe_detail_embed,
    build_recipe_import_embed,
)


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


def test_recipe_detail_embed_splits_long_ingredients() -> None:
    recipe = RecipeDetail(
        identifier="groot-recept",
        title="Groot recept",
        ingredients=[f"Ingrediënt {index} " + ("x" * 200) for index in range(10)],
        instructions=["Bereid alles."],
        servings=None,
        prep_time_minutes=None,
        cook_time_minutes=None,
        total_time_minutes=None,
        source_url=None,
        tags=[],
        meal_types=[],
    )

    embed = build_recipe_detail_embed(recipe)

    ingredient_fields = [
        field for field in embed.fields if field.name.startswith("Ingrediënten")
    ]

    assert len(ingredient_fields) > 1

    assert all(len(field.value) <= 1024 for field in ingredient_fields)


def test_recipe_import_embed_splits_long_warnings() -> None:
    result = RecipeImportResponse(
        import_id="abc123",
        status="partial",
        destination=None,
        recipe=RecipePreview(
            title="Testrecept",
            servings=None,
            prep_time_minutes=None,
            cook_time_minutes=None,
            total_time_minutes=None,
            ingredient_count=1,
            instruction_count=1,
            source_url=None,
        ),
        warnings=[
            {
                "code": f"warning_{index}",
                "message": f"Waarschuwing {index} " + ("x" * 250),
            }
            for index in range(10)
        ],
    )

    embed = build_recipe_import_embed(result)

    warning_fields = [
        field for field in embed.fields if field.name.startswith("Waarschuwingen")
    ]

    assert len(warning_fields) > 1

    assert all(len(field.value) <= 1024 for field in warning_fields)


def test_builds_meal_plan_embed() -> None:
    meal_plan = MealPlan(
        id=10,
        start_date=date(2026, 7, 15),
        end_date=date(2026, 7, 21),
        name="Boodschappenweek",
        entries=[
            MealPlanEntry(
                id=1,
                planned_date=date(2026, 7, 17),
                meal_type="dinner",
                servings=3,
                notes="Extra kaas",
                recipe_identifier="pasta-carbonara",
                recipe_title="Pasta Carbonara",
            ),
            MealPlanEntry(
                id=2,
                planned_date=date(2026, 7, 15),
                meal_type="dinner",
                servings=2,
                notes=None,
                recipe_identifier="tomatensoep",
                recipe_title="Tomatensoep",
            ),
        ],
    )

    embed = build_meal_plan_embed(meal_plan)

    assert embed.title == "Boodschappenweek"
    assert "15-07-2026" in (embed.description or "")
    assert "21-07-2026" in (embed.description or "")
    assert len(embed.fields) == 2
    assert "Tomatensoep" in embed.fields[0].value
    assert "Pasta Carbonara" in embed.fields[1].value
    assert embed.fields[0].name.startswith("Woensdag")
    assert "Entry-ID: `2`" in embed.fields[0].value
    assert "Recept-ID: `tomatensoep`" in embed.fields[0].value
    assert embed.footer.text == "Planning-ID: 10"


def test_meal_plan_embed_handles_empty_plan() -> None:
    meal_plan = MealPlan(
        id=10,
        start_date=date(2026, 7, 15),
        end_date=date(2026, 7, 21),
        name=None,
        entries=[],
    )

    embed = build_meal_plan_embed(meal_plan)

    assert embed.title == "Weekplanning"
    assert len(embed.fields) == 1
    assert embed.fields[0].value == "Er zijn nog geen recepten ingepland."
    assert embed.footer.text == "Planning-ID: 10"
