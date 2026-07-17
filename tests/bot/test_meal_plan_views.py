import asyncio
from datetime import date
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from app.bot.api_client import GeneratedMealPlan, MealPlan
from app.bot.meal_plan_views import GeneratedMealPlanView


def make_result(*, plan_id: int = 42, status: str = "draft") -> GeneratedMealPlan:
    return GeneratedMealPlan(
        plan=MealPlan(
            id=plan_id,
            start_date=date(2026, 7, 22),
            end_date=date(2026, 7, 28),
            name="Voorstel",
            entries=[],
            status=status,
            generation_seed=123,
        ),
        unfilled_slots=[],
        selection_explanations=[],
        generation_seed=123,
    )


def make_interaction(user_id: int = 123):
    interaction = MagicMock()
    interaction.user.id = user_id
    interaction.response.defer = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.edit_original_response = AsyncMock()
    interaction.followup.send = AsyncMock()
    return interaction


def test_generated_plan_view_has_expected_buttons_and_owner_check() -> None:
    view = GeneratedMealPlanView(
        api_client=MagicMock(),
        result=make_result(),
        owner_id=123,
    )
    labels = [
        child.label for child in view.children if isinstance(child, discord.ui.Button)
    ]

    assert labels == ["Accepteren", "Opnieuw genereren", "Annuleren"]
    assert asyncio.run(view.interaction_check(make_interaction(123))) is True
    denied = make_interaction(999)
    assert asyncio.run(view.interaction_check(denied)) is False
    denied.response.send_message.assert_awaited_once()


def test_accept_button_activates_and_disables_buttons() -> None:
    api_client = MagicMock()
    api_client.activate_meal_plan = AsyncMock(
        return_value=make_result(status="active").plan
    )
    view = GeneratedMealPlanView(
        api_client=api_client,
        result=make_result(),
        owner_id=123,
    )
    interaction = make_interaction()

    asyncio.run(view.accept_button.callback(interaction))

    api_client.activate_meal_plan.assert_awaited_once_with(
        plan_id=42,
        activated_by="123",
    )
    assert all(
        child.disabled
        for child in view.children
        if isinstance(child, discord.ui.Button)
    )
    interaction.edit_original_response.assert_awaited_once()


def test_regenerate_button_uses_new_seed_and_updates_preview() -> None:
    api_client = MagicMock()
    api_client.regenerate_meal_plan = AsyncMock(return_value=make_result(plan_id=43))
    view = GeneratedMealPlanView(
        api_client=api_client,
        result=make_result(),
        owner_id=123,
    )
    interaction = make_interaction()

    with patch("app.bot.meal_plan_views.secrets.randbits", return_value=999):
        asyncio.run(view.regenerate_button.callback(interaction))

    api_client.regenerate_meal_plan.assert_awaited_once_with(
        plan_id=42,
        random_seed=999,
    )
    assert view.result.plan.id == 43
    interaction.edit_original_response.assert_awaited_once()

    second_interaction = make_interaction()
    asyncio.run(view.regenerate_button.callback(second_interaction))
    second_interaction.response.send_message.assert_awaited_once_with(
        "Wacht enkele seconden voordat je opnieuw genereert.",
        ephemeral=True,
    )
    assert api_client.regenerate_meal_plan.await_count == 1


def test_cancel_button_deletes_draft_and_disables_buttons() -> None:
    api_client = MagicMock()
    api_client.cancel_meal_plan_draft = AsyncMock()
    view = GeneratedMealPlanView(
        api_client=api_client,
        result=make_result(),
        owner_id=123,
    )
    interaction = make_interaction()

    asyncio.run(view.cancel_button.callback(interaction))

    api_client.cancel_meal_plan_draft.assert_awaited_once_with(plan_id=42)
    assert all(
        child.disabled
        for child in view.children
        if isinstance(child, discord.ui.Button)
    )
