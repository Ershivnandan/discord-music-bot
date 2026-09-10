import json
import urllib.request
import pytest
from unittest.mock import MagicMock
from discord_music_bot.core.downloader import Track
from discord_music_bot.core.playback import GuildPlayer, PlaybackManager
from discord_music_bot.web.health import HealthServer


@pytest.fixture
def web_server():
    # Bind to an available ephemeral port
    bot = MagicMock()
    bot.playback = PlaybackManager(bot)
    player = bot.playback.get_player(999)
    player.playlist = [
        Track(
            title="Web Test Track",
            path="dummy.opus",
            duration=240.0,
            uploader="Web Artist",
            url="https://www.youtube.com/watch?v=web123",
            thumbnail="https://example.com/art.png",
        )
    ]
    player.index = 0

    server = HealthServer(port=8999, bot=bot)
    server.start()
    yield server, 8999


def test_health_endpoints(web_server):
    _, port = web_server

    # 1. Root and /health
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/") as resp:
        assert resp.status == 200
        assert resp.read() == b"Bot is running"

    with urllib.request.urlopen(f"http://127.0.0.1:{port}/health") as resp:
        assert resp.status == 200
        assert resp.read() == b"Bot is running"

    # 2. /player dashboard
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/player") as resp:
        assert resp.status == 200
        body = resp.read().decode("utf-8")
        assert "<title>Discord Music Player — Live Dashboard</title>" in body
        assert "DISCORD AUDIO ENGINE" in body
        assert "equalizer-wave" in body

    # 3. /api/state
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/state") as resp:
        assert resp.status == 200
        data = json.loads(resp.read().decode("utf-8"))
        assert data["active"] is True
        assert data["title"] == "Web Test Track"
        assert data["uploader"] == "Web Artist"
        assert data["duration"] == 240.0
        assert "YouTube" in data["source"]
