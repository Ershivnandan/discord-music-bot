import pytest
from discord_music_bot.core.errors import (
    MusicBotError,
    DownloadError,
    YouTubeBlockedError,
    VoiceChannelError,
    PlaybackError,
    QueueError,
)
from discord_music_bot.core.logger import BotLogger


def test_error_hierarchy():
    err = YouTubeBlockedError(detail="Sign in to confirm you are not a bot")
    assert isinstance(err, DownloadError)
    assert isinstance(err, MusicBotError)
    assert err.code == "ERR_YOUTUBE_BLOCKED"
    assert err.detail == "Sign in to confirm you are not a bot"


def test_embed_generation():
    err = VoiceChannelError("You are not connected to a voice channel.", detail="Join a voice channel first")
    embed = err.to_embed()
    assert embed.title is not None
    assert "ERR_VOICE_REQUIRED" in embed.title
    assert embed.description == "You are not connected to a voice channel."
    assert len(embed.fields) >= 1
    assert embed.fields[0].name == "Details"
    assert "Join a voice channel first" in embed.fields[0].value


def test_logger_integration():
    logger = BotLogger("test_errors")
    err = QueueError("Queue is empty", guild_id=123456789)
    # Verify logging does not raise
    err.log_with(logger)
