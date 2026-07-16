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


async def ensure_allowed_role(
    interaction: discord.Interaction,
    allowed_role_ids: set[int],
) -> bool:
    if not allowed_role_ids:
        return True

    member = interaction.user

    if not isinstance(member, discord.Member):
        await interaction.response.send_message(
            "Ik kon je serverrollen niet controleren.",
            ephemeral=True,
        )
        return False

    member_role_ids = {role.id for role in member.roles}

    if member_role_ids.isdisjoint(allowed_role_ids):
        await interaction.response.send_message(
            "Je hebt geen toestemming om deze actie uit te voeren.",
            ephemeral=True,
        )
        return False

    return True
