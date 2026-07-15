from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

from app.models.recipe import Ingredient, Recipe, SourceType
from app.services.markdown_renderer import RecipeMarkdownRenderer


def make_recipe() -> Recipe:
    return Recipe(
        title="Pasta Carbonara",
        source_type=SourceType.WEBSITE,
        source_url="https://example.com/carbonara",
        ingredients=[Ingredient(name="spaghetti")],
        instructions=["Cook the pasta."],
    )


def make_snapshot_recipe() -> Recipe:
    return Recipe(
        id=UUID("11111111-1111-1111-1111-111111111111"),
        import_id=UUID("22222222-2222-2222-2222-222222222222"),
        content_hash="abc123",
        imported_at=datetime(
            2026,
            7,
            15,
            8,
            30,
            tzinfo=UTC,
        ),
        title="Pasta Carbonara",
        source_type=SourceType.WEBSITE,
        source_url="https://example.com/carbonara",
        servings=4,
        ingredients=[
            Ingredient(
                name="spaghetti",
                quantity=Decimal("400"),
                unit="g",
            ),
            Ingredient(
                name="peterselie",
                quantity=Decimal("1"),
                unit="el",
                optional=True,
            ),
        ],
        instructions=[
            "Cook the pasta.",
            "Mix everything.",
        ],
        tags=["pasta", "quick"],
    )


def test_renderer_creates_recipe_markdown() -> None:
    import_id = uuid4()
    recipe = Recipe(
        import_id=import_id,
        content_hash="abc123",
        title="Pasta Carbonara",
        source_type=SourceType.WEBSITE,
        source_url="https://example.com/carbonara",
        servings=4,
        ingredients=[
            Ingredient(
                name="spaghetti",
                quantity=Decimal("400"),
                unit="g",
            ),
            Ingredient(
                name="peterselie",
                quantity=Decimal("1"),
                unit="el",
                optional=True,
            ),
        ],
        instructions=[
            "Cook the pasta.",
            "Mix everything.",
        ],
        tags=["pasta", "quick"],
    )

    markdown = RecipeMarkdownRenderer().render(recipe)

    assert "# Pasta Carbonara" in markdown
    assert "- 400 g spaghetti" in markdown
    assert "- 1 el peterselie _(optioneel)_" in markdown
    assert "1. Cook the pasta." in markdown
    assert "source_type: website" in markdown
    assert "tags:" in markdown
    assert f"id: {recipe.id}" in markdown
    assert f"import_id: {import_id}" in markdown
    assert "content_hash: abc123" in markdown


def test_renderer_handles_recipe_without_import_id() -> None:
    recipe = make_recipe()

    markdown = RecipeMarkdownRenderer().render(recipe)

    assert "import_id: null" in markdown


def test_renderer_matches_markdown_snapshot() -> None:
    recipe = make_snapshot_recipe()
    renderer = RecipeMarkdownRenderer()

    markdown = renderer.render(recipe)

    snapshot_path = Path(__file__).parents[1] / "snapshots" / "pasta_carbonara.md"
    expected = snapshot_path.read_text(encoding="utf-8")

    assert markdown == expected
