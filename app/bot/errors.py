import logging

import discord
from discord import app_commands

from app.bot.constants import NOTICE_EPHEMERAL

logger = logging.getLogger(__name__)


async def handle_app_command_error(
    interaction: discord.Interaction,
    error: app_commands.AppCommandError,
) -> None:
    if isinstance(error, app_commands.CommandOnCooldown):
        message = (
            "Je voert dit commando iets te snel uit. "
            f"Probeer het over {error.retry_after:.0f} seconden opnieuw."
        )

        if interaction.response.is_done():
            await interaction.followup.send(
                message,
                ephemeral=NOTICE_EPHEMERAL,
            )
        else:
            await interaction.response.send_message(
                message,
                ephemeral=NOTICE_EPHEMERAL,
            )

        return

    logger.exception(
        "Unexpected Discord application command error",
        exc_info=error,
    )

    message = "Er ging onverwacht iets mis."

    if interaction.response.is_done():
        await interaction.followup.send(
            message,
            ephemeral=NOTICE_EPHEMERAL,
        )
    else:
        await interaction.response.send_message(
            message,
            ephemeral=NOTICE_EPHEMERAL,
        )
