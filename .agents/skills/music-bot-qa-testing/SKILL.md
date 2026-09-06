---
name: music-bot-qa-testing
description: >-
  Use this skill when writing or running automated tests, mocking Discord voice clients,
  simulating yt-dlp download responses, testing rapid user button clicks, validating queue
  transitions, or injecting audio stream network errors.
---

# Music Bot QA Testing Skill

This skill provides procedures and patterns for writing, running, and debugging automated unit and integration tests for the Discord Music Bot.

## Test Environment Setup

Tests run in isolated environments without requiring an active Discord bot token or physical voice connections.

Install test dependencies with `uv`:
```sh
uv add --dev pytest pytest-asyncio
uv run pytest
```

## Mocking Voice Client & Downloader Patterns

### 1. Mocking `discord.VoiceClient`
Because Discord voice requires UDP/gateway connections, mock `VoiceClient` during unit testing:
```python
import unittest.mock as mock
import pytest

@pytest.fixture
def mock_voice_client():
    vc = mock.AsyncMock()
    vc.is_playing.return_value = False
    vc.is_paused.return_value = False
    vc.channel = mock.Mock()
    return vc
```

### 2. Mocking `SongDownloader`
Avoid downloading real multi-megabyte audio files during tests by mocking `download_async`:
```python
@pytest.fixture
def mock_downloader(monkeypatch, tmp_path):
    dummy_audio = tmp_path / "test_song.opus"
    dummy_audio.write_bytes(b"dummy audio data")

    async def fake_download(search):
        return ("Test Song Title", str(dummy_audio), False)

    monkeypatch.setattr(
        "discord_music_bot.core.downloader.SongDownloader.download_async",
        fake_download
    )
```

## Key Test Scenarios to Validate

1. **Generation Token Under Rapid Skips**:
   - Call `play_index(0)` then immediately simulate a manual `play_index(1)` skip.
   - Trigger the `after_playing` callback of index 0.
   - Assert that the callback aborts and does *not* skip index 1.
2. **Temporary File Cleanup**:
   - Verify that calling `disconnect_and_cleanup()` removes audio files created in `tempfile.gettempdir() / "discord-music"`.
3. **Speed Boundary Checks**:
   - Verify valid speeds (`1`, `2`, `3`) apply the corresponding FFmpeg filters (`SPEED_FILTERS`).
   - Verify unsupported speeds (e.g. `0`, `4`) are rejected with user-friendly messages.
4. **Fallback Propagation**:
   - Verify that when `yt-dlp` raises `DownloadError`, the downloader queries `https://www.youtube.com/oembed` and falls back to `scsearch`.
