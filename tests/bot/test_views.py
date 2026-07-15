import discord
from app.bot.api_client import RecipeApiClient
from app.bot.views import RecipeImportView


def test_recipe_import_view_contains_save_and_cancel_buttons() -> None:
    view = RecipeImportView(
        api_client=RecipeApiClient(base_url="http://example.test"),
        source_url="https://example.com/pasta",
        owner_id=123,
    )

    buttons = [child for child in view.children if isinstance(child, discord.ui.Button)]

    assert [button.label for button in buttons] == [
        "Opslaan",
        "Annuleren",
    ]


def test_disable_all_buttons() -> None:
    view = RecipeImportView(
        api_client=RecipeApiClient(base_url="http://example.test"),
        source_url="https://example.com/pasta",
        owner_id=123,
    )

    view._disable_all_buttons()

    assert all(
        child.disabled
        for child in view.children
        if isinstance(child, discord.ui.Button)
    )
