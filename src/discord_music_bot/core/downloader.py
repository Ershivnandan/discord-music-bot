"""Song downloads via yt-dlp."""

import asyncio
import re
import urllib.parse

import aiohttp
import yt_dlp

from ..config import YDL_OPTIONS
from .errors import DownloadError as BotDownloadError, YouTubeBlockedError
from .logger import BotLogger

YOUTUBE_URL_RE = re.compile(r"https?://(?:www\.|m\.|music\.)?(?:youtube\.com|youtu\.be)/")


class SongDownloader:
    """Downloads a song to the local cache directory before playback."""

    def __init__(self, options: dict = YDL_OPTIONS):
        self.options = options
        self.logger = BotLogger("downloader")

    def download(self, search: str):
        self.logger.info(f"Starting download for query/URL: {search}")
        try:
            with yt_dlp.YoutubeDL(self.options) as ydl:
                info = ydl.extract_info(search, download=True)
                if not info:
                    raise BotDownloadError(f"No stream found for: {search}")
                if "entries" in info:  # came from a search
                    entries = [e for e in info.get("entries", []) if e]
                    if not entries:
                        raise BotDownloadError(f"No search results found for: {search}")
                    info = entries[0]
                title = info.get("title", "Unknown title")
                filename = ydl.prepare_filename(info)
                self.logger.info(f"Download complete: {title} (saved to {filename})")
                return title, filename
        except yt_dlp.utils.DownloadError:
            raise
        except BotDownloadError:
            raise
        except Exception as e:
            raise BotDownloadError(f"Failed while downloading: {search}", detail=str(e)) from e

    async def download_async(self, search: str):
        """Returns (title, path, used_fallback, blocked_error)."""
        try:
            # yt-dlp is blocking; run it off the event loop
            title, path = await asyncio.to_thread(self.download, search)
            return title, path, False, None
        except yt_dlp.utils.DownloadError as e:
            err_raw = str(e).strip()
            err_lines = [line.strip() for line in err_raw.splitlines() if line.strip()]
            err_summary = err_lines[-1] if err_lines else err_raw
            if "ERROR: [youtube]" in err_summary:
                err_summary = err_summary.split("ERROR: [youtube]")[-1].strip(": ")

            # YouTube bot-checks datacenter IPs. oEmbed still answers from
            # them, so grab the video title and find the song on SoundCloud.
            title = await self._youtube_title(search)
            if title is None:
                self.logger.error(f"Failed to extract title via oEmbed for {search}: {e}", exc_info=True)
                raise BotDownloadError(f"Unable to download '{search}'", detail=err_summary) from e

            blocked_err = YouTubeBlockedError(detail=err_summary)
            self.logger.warning(
                f"YouTube download failed for {search}: {err_raw}. Falling back to SoundCloud search for title: {title}"
            )
            # YouTube titles are noisy ("Song | Artist | Cast | Label"); the
            # first couple of segments search much better than the whole thing
            query = " ".join(part.strip() for part in title.split("|")[:2])
            try:
                title, path = await asyncio.to_thread(self.download, f"scsearch:{query[:100]}")
                return title, path, True, blocked_err
            except Exception as sc_err:
                sc_msg = getattr(sc_err, "detail", None) or str(sc_err)
                raise BotDownloadError(
                    f"YouTube blocked download ({err_summary}) and SoundCloud search found no match",
                    detail=f"YouTube: {err_summary}\nSoundCloud fallback: {sc_msg}",
                ) from sc_err



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
