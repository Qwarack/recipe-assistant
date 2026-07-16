from unittest.mock import AsyncMock, Mock, patch

from app.bot.checks import ensure_allowed_channel, ensure_allowed_role


async def test_allows_matching_channel() -> None:
    interaction = Mock()
    interaction.channel_id = 123
    interaction.response.send_message = AsyncMock()

    allowed = await ensure_allowed_channel(
        interaction,
        allowed_channel_id=123,
    )

    assert allowed is True
    interaction.response.send_message.assert_not_called()


async def test_allows_all_channels_when_not_configured() -> None:
    interaction = Mock()
    interaction.channel_id = 999
    interaction.response.send_message = AsyncMock()

    allowed = await ensure_allowed_channel(
        interaction,
        allowed_channel_id=None,
    )

    assert allowed is True
    interaction.response.send_message.assert_not_called()


async def test_rejects_different_channel() -> None:
    interaction = Mock()
    interaction.channel_id = 999
    interaction.response.send_message = AsyncMock()

    allowed = await ensure_allowed_channel(
        interaction,
        allowed_channel_id=123,
    )

    assert allowed is False

    interaction.response.send_message.assert_awaited_once_with(
        "Dit commando mag alleen in het ingestelde receptenkanaal worden gebruikt.",
        ephemeral=True,
    )


async def test_allows_role_when_no_roles_are_configured() -> None:
    interaction = Mock()
    interaction.response.send_message = AsyncMock()

    allowed = await ensure_allowed_role(
        interaction,
        allowed_role_ids=set(),
    )

    assert allowed is True
    interaction.response.send_message.assert_not_called()


async def test_rejects_user_when_roles_cannot_be_checked() -> None:
    interaction = Mock()
    interaction.user = Mock()
    interaction.response.send_message = AsyncMock()

    allowed = await ensure_allowed_role(
        interaction,
        allowed_role_ids={222},
    )

    assert allowed is False
    interaction.response.send_message.assert_awaited_once_with(
        "Ik kon je serverrollen niet controleren.",
        ephemeral=True,
    )


async def test_allows_member_with_matching_role() -> None:
    member = Mock()
    member.roles = [
        Mock(id=111),
        Mock(id=222),
    ]
    interaction = Mock()
    interaction.user = member
    interaction.response.send_message = AsyncMock()

    with patch(
        "app.bot.checks.discord.Member",
        new=type(member),
    ):
        allowed = await ensure_allowed_role(
            interaction,
            allowed_role_ids={222, 333},
        )

    assert allowed is True
    interaction.response.send_message.assert_not_called()


async def test_rejects_member_without_matching_role() -> None:
    member = Mock()
    member.roles = [
        Mock(id=111),
    ]
    interaction = Mock()
    interaction.user = member
    interaction.response.send_message = AsyncMock()

    with patch(
        "app.bot.checks.discord.Member",
        new=type(member),
    ):
        allowed = await ensure_allowed_role(
            interaction,
            allowed_role_ids={222},
        )

    assert allowed is False
    interaction.response.send_message.assert_awaited_once_with(
        "Je hebt geen toestemming om deze actie uit te voeren.",
        ephemeral=True,
    )
