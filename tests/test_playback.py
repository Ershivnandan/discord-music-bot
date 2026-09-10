import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from discord_music_bot.core.playback import GuildPlayer, PlaybackManager


def test_guild_player_initial_position():
    player = GuildPlayer()
    assert player.position == 0.0
    assert player.play_start_time is None
    assert player.is_paused is False
    assert player.get_current_position() == 0.0


def test_guild_player_position_advancement(monkeypatch):
    player = GuildPlayer()
    start = 100.0
    monkeypatch.setattr(time, "monotonic", lambda: start)
    player.position = 10.0
    player.play_start_time = start
    player.speed = 1

    # After 5 seconds at 1x speed
    monkeypatch.setattr(time, "monotonic", lambda: start + 5.0)
    assert player.get_current_position() == pytest.approx(15.0)

    # After 5 seconds at 2x speed
    player.speed = 2
    assert player.get_current_position() == pytest.approx(20.0)


def test_guild_player_pause_and_resume(monkeypatch):
    player = GuildPlayer()
    start = 100.0
    monkeypatch.setattr(time, "monotonic", lambda: start)
    player.position = 0.0
    player.play_start_time = start
    player.speed = 1

    # Play for 10 seconds
    monkeypatch.setattr(time, "monotonic", lambda: start + 10.0)
    assert player.get_current_position() == pytest.approx(10.0)

    # Pause at 10 seconds
    player.pause()
    assert player.is_paused is True
    assert player.position == pytest.approx(10.0)
    assert player.play_start_time is None

    # While paused, 20 seconds pass in real time
    monkeypatch.setattr(time, "monotonic", lambda: start + 30.0)
    assert player.get_current_position() == pytest.approx(10.0)

    # Resume at t = 130
    player.resume()
    assert player.is_paused is False
    assert player.play_start_time == start + 30.0

    # Play for another 5 seconds at 2x
    player.speed = 2
    monkeypatch.setattr(time, "monotonic", lambda: start + 35.0)
    assert player.get_current_position() == pytest.approx(20.0)  # 10.0 + (5.0 * 2)


@pytest.mark.asyncio
async def test_play_index_ffmpeg_before_options(monkeypatch):
    bot = MagicMock()
    manager = PlaybackManager(bot)
    ctx = MagicMock()
    ctx.guild.id = 12345
    voice = MagicMock()
    voice.is_playing.return_value = False
    voice.is_paused.return_value = False
    ctx.voice_client = voice

    player = manager.get_player(12345)
    player.playlist = [("Test Track", "dummy_path.opus")]

    with patch("discord_music_bot.core.playback.discord.FFmpegOpusAudio") as mock_ffmpeg, \
         patch.object(manager, "refresh_player", new=AsyncMock()):

        # Start from beginning
        await manager.play_index(ctx, 0, start_time=0.0)
        mock_ffmpeg.assert_called_with(
            "dummy_path.opus",
            before_options=None,
            options="-vn",
        )
        assert player.position == 0.0

        # Change speed with seeking: start_time = 42.5s at 2x speed
        player.speed = 2
        await manager.play_index(ctx, 0, start_time=42.5)
        mock_ffmpeg.assert_called_with(
            "dummy_path.opus",
            before_options="-ss 42.50",
            options="-vn -filter:a atempo=2.0",
        )
        assert player.position == 42.5


@pytest.mark.asyncio
async def test_set_speed_preserves_timestamp(monkeypatch):
    bot = MagicMock()
    manager = PlaybackManager(bot)
    ctx = MagicMock()
    ctx.guild.id = 99999
    voice = MagicMock()
    voice.is_playing.return_value = True
    voice.is_paused.return_value = False
    ctx.voice_client = voice

    player = manager.get_player(99999)
    player.playlist = [("Speedy Song", "speedy.opus")]
    player.index = 0
    player.speed = 1

    start = 50.0
    monkeypatch.setattr(time, "monotonic", lambda: start)
    player.position = 0.0
    player.play_start_time = start

    # 15 seconds pass at 1x
    monkeypatch.setattr(time, "monotonic", lambda: start + 15.0)

    with patch.object(manager, "play_index", new=AsyncMock()) as mock_play_index:
        await manager.set_speed(ctx, 2)
        assert player.speed == 2
        # play_index should be called with current_pos = 15.0
        mock_play_index.assert_called_once_with(ctx, 0, start_time=pytest.approx(15.0))


@pytest.mark.asyncio
async def test_speed_roundtrip_preserves_position(monkeypatch):
    """Test switching 1x -> 2x -> 1x preserves accurate playback position."""
    bot = MagicMock()
    manager = PlaybackManager(bot)
    ctx = MagicMock()
    ctx.guild.id = 88888
    voice = MagicMock()
    voice.is_playing.return_value = True
    voice.is_paused.return_value = False
    ctx.voice_client = voice

    player = manager.get_player(88888)
    player.playlist = [("Roundtrip Song", "roundtrip.opus")]
    player.index = 0
    player.speed = 1

    t0 = 200.0
    monkeypatch.setattr(time, "monotonic", lambda: t0)
    player.position = 0.0
    player.play_start_time = t0

    # 10s pass at 1x -> position is 10s
    t1 = t0 + 10.0
    monkeypatch.setattr(time, "monotonic", lambda: t1)

    with patch.object(manager, "play_index", new=AsyncMock()) as mock_play:
        # Switch to 2x
        await manager.set_speed(ctx, 2)
        mock_play.assert_called_with(ctx, 0, start_time=pytest.approx(10.0))
        # Simulate play_index updating player position & start time
        player.position = 10.0
        player.play_start_time = t1

    # 10 real seconds pass at 2x -> 20s of song played -> song timestamp is 30s
    t2 = t1 + 10.0
    monkeypatch.setattr(time, "monotonic", lambda: t2)
    assert player.get_current_position() == pytest.approx(30.0)

    with patch.object(manager, "play_index", new=AsyncMock()) as mock_play:
        # Switch back to 1x
        await manager.set_speed(ctx, 1)
        # Should seek to 30.0s!
        mock_play.assert_called_with(ctx, 0, start_time=pytest.approx(30.0))
        player.position = 30.0
        player.play_start_time = t2

    # 5s pass at 1x -> song timestamp is 35s
    t3 = t2 + 5.0
    monkeypatch.setattr(time, "monotonic", lambda: t3)
    assert player.get_current_position() == pytest.approx(35.0)


@pytest.mark.asyncio
async def test_playback_manager_pause_and_resume():
    bot = MagicMock()
    manager = PlaybackManager(bot)
    ctx = MagicMock()
    ctx.guild.id = 77777
    voice = MagicMock()
    voice.is_playing.return_value = True
    voice.is_paused.return_value = False
    ctx.voice_client = voice

    player = manager.get_player(77777)
    player.position = 5.0
    player.play_start_time = time.monotonic()

    with patch.object(manager, "refresh_player", new=AsyncMock()):
        await manager.pause(ctx)
        assert player.is_paused is True
        voice.pause.assert_called_once()

        voice.is_playing.return_value = False
        voice.is_paused.return_value = True

        await manager.resume(ctx)
        assert player.is_paused is False
        voice.resume.assert_called_once()


@pytest.mark.asyncio
async def test_progress_task_cancellation():
    player = GuildPlayer()
    task = asyncio.create_task(asyncio.sleep(10))
    player.progress_task = task
    assert not task.cancelled()

    player.cancel_progress_task()
    await asyncio.sleep(0)
    assert task.cancelled()
    assert player.progress_task is None


@pytest.mark.asyncio
async def test_progress_updater_edits_message(monkeypatch):
    bot = MagicMock()
    manager = PlaybackManager(bot)
    ctx = MagicMock()
    ctx.guild.id = 12345
    voice = MagicMock()
    voice.is_connected.return_value = True
    voice.is_playing.return_value = True
    ctx.guild.voice_client = voice

    player = manager.get_player(12345)
    player.playlist = [("Test Track", "test.opus")]
    player.index = 0
    player.generation = 1

    mock_msg = AsyncMock()
    player.message = mock_msg

    import discord_music_bot.core.playback as pb_mod
    monkeypatch.setattr(pb_mod, "PROGRESS_UPDATE_INTERVAL", 0.05)

    # Start updater in background
    task = asyncio.create_task(manager._progress_updater(ctx, player, generation=1))
    await asyncio.sleep(0.12)  # Allow at least 1-2 ticks
    assert mock_msg.edit.call_count >= 1

    # Invalidate generation to stop loop
    player.generation = 2
    await asyncio.sleep(0.08)
    assert task.done()


