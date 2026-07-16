import asyncio
from unittest.mock import AsyncMock, MagicMock

from app.bot.errors import handle_app_command_error
from discord import app_commands


def test_cooldown_error_uses_initial_interaction_response() -> None:
    interaction = MagicMock()
    interaction.response.is_done.return_value = False
    interaction.response.send_message = AsyncMock()
    interaction.followup.send = AsyncMock()
    error = app_commands.CommandOnCooldown(
        app_commands.Cooldown(2, 60.0),
        retry_after=12.6,
    )

    asyncio.run(handle_app_command_error(interaction, error))

    interaction.response.send_message.assert_awaited_once_with(
        (
            "Je voert dit commando iets te snel uit. "
            "Probeer het over 13 seconden opnieuw."
        ),
        ephemeral=True,
    )
    interaction.followup.send.assert_not_awaited()


def test_cooldown_error_uses_followup_after_response() -> None:
    interaction = MagicMock()
    interaction.response.is_done.return_value = True
    interaction.response.send_message = AsyncMock()
    interaction.followup.send = AsyncMock()
    error = app_commands.CommandOnCooldown(
        app_commands.Cooldown(2, 60.0),
        retry_after=4.2,
    )

    asyncio.run(handle_app_command_error(interaction, error))

    interaction.followup.send.assert_awaited_once_with(
        (
            "Je voert dit commando iets te snel uit. "
            "Probeer het over 4 seconden opnieuw."
        ),
        ephemeral=True,
    )
    interaction.response.send_message.assert_not_awaited()
