from unittest.mock import AsyncMock, Mock

from app.bot.checks import ensure_allowed_channel


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
