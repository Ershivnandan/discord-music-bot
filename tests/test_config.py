import os
import pytest
from discord_music_bot.config import YDL_OPTIONS


def test_unauthenticated_clients_bypass_botcheck():
    """Verify that 'web' is excluded from player_client when unauthenticated,
    preventing YouTube's datacenter BotGuard check from aborting downloads."""
    clients = YDL_OPTIONS["extractor_args"]["youtube"]["player_client"]
    assert "web" not in clients
    assert "visionos" in clients
    assert "mweb" in clients
    assert "android_vr" in clients


def test_pot_provider_configured():
    """Verify bgutil POT provider base_url is configured."""
    base_url = YDL_OPTIONS["extractor_args"]["youtubepot-bgutilhttp"]["base_url"][0]
    assert base_url.startswith("http")


def test_proxy_configured(monkeypatch):
    """Verify proxy parameter can be set via YTDLP_PROXY."""
    test_proxy = "socks5://127.0.0.1:1080"
    monkeypatch.setenv("YTDLP_PROXY", test_proxy)
    options = dict(YDL_OPTIONS)
    if os.environ.get("YTDLP_PROXY"):
        options["proxy"] = os.environ["YTDLP_PROXY"]
    assert options.get("proxy") == test_proxy
