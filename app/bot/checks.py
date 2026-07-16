import discord


async def ensure_allowed_channel(
    interaction: discord.Interaction,
    allowed_channel_id: int | None,
) -> bool:
    if allowed_channel_id is None:
        return True

    if interaction.channel_id == allowed_channel_id:
        return True

    await interaction.response.send_message(
        "Dit commando mag alleen in het ingestelde receptenkanaal worden gebruikt.",
        ephemeral=True,
    )

    return False
