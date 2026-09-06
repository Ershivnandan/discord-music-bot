from unittest.mock import MagicMock
import pytest
from discord_music_bot.core.downloader import Track
from discord_music_bot.core.playback import GuildPlayer, PlaybackManager
from discord_music_bot.ui.player_card import (
    build_embed,
    format_duration,
    make_progress_bar,
    PlayerView,
)


def test_format_duration():
    assert format_duration(None) == "00:00"
    assert format_duration(-5) == "00:00"
    assert format_duration(0) == "00:00"
    assert format_duration(45) == "00:45"
    assert format_duration(65) == "01:05"
    assert format_duration(3665) == "01:01:05"


def test_make_progress_bar():
    # Without duration / stream
    bar_none = make_progress_bar(30, None)
    assert "00:30 / --:--" in bar_none

    # Normal progress
    bar = make_progress_bar(50, 100, length=10)
    assert "`00:50`" in bar
    assert "`01:40`" in bar
    assert "🔘" in bar

    # Start and end bounds
    bar_start = make_progress_bar(0, 200, length=10)
    assert bar_start.startswith("`00:00` 🔘")

    bar_end = make_progress_bar(200, 200, length=10)
    assert "🔘 `03:20`" in bar_end


def test_build_embed_idle():
    player = GuildPlayer()
    guild = MagicMock()
    guild.icon = None
    guild.voice_client = None

    embed = build_embed(player, guild)
    assert embed.title == "🎵 Discord Music Player"
    assert "Idle" in embed.fields[0].value


def test_build_embed_playing_track():
    player = GuildPlayer()
    track = Track(
        title="Epic Song",
        path="song.opus",
        duration=180.0,
        thumbnail="https://example.com/art.jpg",
        uploader="Super Artist",
        url="https://youtube.com/watch?v=12345",
        requester="Shiv",
    )
    player.playlist = [track]
    player.index = 0
    player.position = 45.0

    guild = MagicMock()
    guild.icon = None
    voice = MagicMock()
    voice.is_playing.return_value = True
    voice.is_paused.return_value = False
    guild.voice_client = voice

    embed = build_embed(player, guild)
    assert embed.color.value == 0x2ECC71  # Playing Emerald
    assert "Epic Song" in embed.description
    assert "Super Artist" in embed.description
    assert "Requested by Shiv" in embed.description
    assert embed.thumbnail.url == "https://example.com/art.jpg"
    assert "Playing" in embed.fields[0].value
    assert "1.0x" in embed.fields[1].value


def test_player_view_button_layout_and_states():
    bot = MagicMock()
    playback = PlaybackManager(bot)
    player = playback.get_player(1111)
    player.playlist = [
        Track("Song 1", "s1.opus"),
        Track("Song 2", "s2.opus"),
        Track("Song 3", "s3.opus"),
    ]
    player.index = 0
    player.speed = 2
    player.loop_mode = "track"

    view = PlayerView(playback, 1111)
    # Total buttons: 5 in row 0, 5 in row 1
    assert len(view.children) == 10

    # Speed 2x should be primary
    assert view.speed2_button.style.value == 1  # ButtonStyle.primary

    # Prev button disabled at index 0
    assert view.prev_button.disabled is True

    # Loop button should show Track
    assert "Track" in view.loop_button.label

    # Next button enabled because more tracks exist
    assert view.next_button.disabled is False

    # Shuffle button enabled because 2 upcoming songs exist
    assert view.shuffle_button.disabled is False
