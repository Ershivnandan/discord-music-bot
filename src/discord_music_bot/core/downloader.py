"""Song downloads via yt-dlp."""

import asyncio
import re
import urllib.parse

import aiohttp
import yt_dlp

from ..config import YDL_OPTIONS

YOUTUBE_URL_RE = re.compile(r"https?://(?:www\.|m\.|music\.)?(?:youtube\.com|youtu\.be)/")


class SongDownloader:
    """Downloads a song to the local cache directory before playback."""

    def __init__(self, options: dict = YDL_OPTIONS):
        self.options = options

    def download(self, search: str):
        with yt_dlp.YoutubeDL(self.options) as ydl:
            info = ydl.extract_info(search, download=True)
            if "entries" in info:  # came from a search
                info = info["entries"][0]
            return info.get("title", "Unknown title"), ydl.prepare_filename(info)

    async def download_async(self, search: str):
        """Returns (title, path, used_fallback)."""
        try:
            # yt-dlp is blocking; run it off the event loop
            title, path = await asyncio.to_thread(self.download, search)
            return title, path, False
        except yt_dlp.utils.DownloadError as e:
            # YouTube bot-checks datacenter IPs. oEmbed still answers from
            # them, so grab the video title and find the song on SoundCloud.
            title = await self._youtube_title(search)
            if title is None:
                raise
            print(f"YouTube download failed, falling back to SoundCloud: {str(e)[:300]}")
            # YouTube titles are noisy ("Song | Artist | Cast | Label"); the
            # first couple of segments search much better than the whole thing
            query = " ".join(part.strip() for part in title.split("|")[:2])
            title, path = await asyncio.to_thread(self.download, f"scsearch:{query[:100]}")
            return title, path, True

    async def _youtube_title(self, url: str):
        if not YOUTUBE_URL_RE.match(url):
            return None
        api = "https://www.youtube.com/oembed?" + urllib.parse.urlencode(
            {"url": url, "format": "json"}
        )
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(api, timeout=aiohttp.ClientTimeout(total=15)) as resp:
                    if resp.status != 200:
                        return None
                    data = await resp.json()
                    return data.get("title")
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return None
