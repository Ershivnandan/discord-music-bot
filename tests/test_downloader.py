import pytest
from unittest.mock import patch, MagicMock
from discord_music_bot.core.downloader import SongDownloader
from discord_music_bot.core.errors import DownloadError, YouTubeBlockedError


@pytest.mark.asyncio
async def test_youtube_title_oembed():
    downloader = SongDownloader()
    # Test valid YouTube URL format extraction
    url = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
    title = await downloader._youtube_title(url)
    assert title is not None
    assert "Rick Astley" in title or "Never Gonna Give You Up" in title


@pytest.mark.asyncio
async def test_non_youtube_url_title():
    downloader = SongDownloader()
    title = await downloader._youtube_title("https://soundcloud.com/artist/track")
    assert title is None


@pytest.mark.asyncio
async def test_downloader_fallback_on_block(monkeypatch):
    downloader = SongDownloader()

    import yt_dlp.utils
    def fail_download(search):
        raise yt_dlp.utils.DownloadError("Sign in to confirm you're not a bot. Use --cookies-from-browser")

    monkeypatch.setattr(downloader, "download", fail_download)

    # When YouTube fails, it should attempt oEmbed title lookup
    # Mock _youtube_title to return a dummy title and mock second download call to succeed
    call_count = 0
    def mock_download(query):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise yt_dlp.utils.DownloadError("ERROR: [youtube] Sign in to confirm you're not a bot")
        return ("Fallback Song", "/tmp/fallback.opus")

    monkeypatch.setattr(downloader, "download", mock_download)
    
    title, path, used_fallback, blocked_err = await downloader.download_async("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
    assert used_fallback is True
    assert isinstance(blocked_err, YouTubeBlockedError)
    assert "Fallback Song" in title
