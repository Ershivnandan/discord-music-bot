import os
import pytest
from discord_music_bot.config import BotConfig, YDL_OPTIONS


def test_unauthenticated_clients_bypass_botcheck():
    clients = YDL_OPTIONS["extractor_args"]["youtube"]["player_client"]
    assert "web" not in clients
    assert "tv" in clients
    assert "web_embedded" in clients
    assert "visionos" in clients
    assert "mweb" in clients
    assert "android_vr" in clients


def test_pot_provider_configured():
    base_url = YDL_OPTIONS["extractor_args"]["youtubepot-bgutilhttp"]["base_url"][0]
    assert base_url.startswith("http")


def test_proxy_configured(monkeypatch):
    test_proxy = "socks5://127.0.0.1:1080"
    monkeypatch.setenv("YTDLP_PROXY", test_proxy)
    options = BotConfig.get_ydl_options()
    assert options.get("proxy") == test_proxy


def test_no_cookies_in_ydl_options():
    options = BotConfig.get_ydl_options()
    assert "cookiefile" not in options
    assert "cookiesfrombrowser" not in options
