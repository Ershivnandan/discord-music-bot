"""Song downloads via yt-dlp."""

import asyncio
import re
import urllib.parse

import aiohttp
import yt_dlp

from dataclasses import dataclass
from typing import Optional

from ..config import YDL_OPTIONS
from .errors import DownloadError as BotDownloadError, YouTubeBlockedError
from .logger import BotLogger

YOUTUBE_URL_RE = re.compile(r"https?://(?:www\.|m\.|music\.)?(?:youtube\.com|youtu\.be)/")


@dataclass
class Track:
    title: str
    path: str
    duration: Optional[float] = None
    thumbnail: Optional[str] = None
    uploader: Optional[str] = None
    url: Optional[str] = None
    requester: Optional[str] = None

    def __str__(self) -> str:
        return self.title

    def __contains__(self, item: str) -> bool:
        return item in self.title

    def __eq__(self, other) -> bool:
        if isinstance(other, str):
            return self.title == other
        if isinstance(other, Track):
            return self.title == other.title and self.path == other.path
        return False

    def __getitem__(self, idx: int):
        if idx == 0:
            return self.title
        elif idx == 1:
            return self.path
        raise IndexError("Track index out of range")

    def __len__(self) -> int:
        return 2

    def __iter__(self):
        yield self.title
        yield self.path


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
                duration = info.get("duration")
                thumbnail = info.get("thumbnail")
                uploader = info.get("uploader") or info.get("channel") or info.get("artist")
                url = info.get("webpage_url") or info.get("original_url")
                filename = ydl.prepare_filename(info)
                self.logger.info(f"Download complete: {title} (saved to {filename})")
                return Track(
                    title=title,
                    path=filename,
                    duration=duration,
                    thumbnail=thumbnail,
                    uploader=uploader,
                    url=url,
                )
        except yt_dlp.utils.DownloadError:
            raise
        except BotDownloadError:
            raise
        except Exception as e:
            raise BotDownloadError(f"Failed while downloading: {search}", detail=str(e)) from e

    async def download_async(self, search: str):
        """Returns (track, path, used_fallback, blocked_error)."""
        try:
            # yt-dlp is blocking; run it off the event loop
            res = await asyncio.to_thread(self.download, search)
            track = res if isinstance(res, Track) else Track(title=res[0], path=res[1])
            return track, track.path, False, None
        except yt_dlp.utils.DownloadError as e:
            err_raw = str(e).strip()
            err_lines = [line.strip() for line in err_raw.splitlines() if line.strip()]
            err_summary = err_lines[-1] if err_lines else err_raw
            if "ERROR: [youtube]" in err_summary:
                err_summary = err_summary.split("ERROR: [youtube]")[-1].strip(": ")

            # YouTube bot-checks datacenter IPs. oEmbed still answers from
            # them, so grab the video title and metadata to find on SoundCloud.
            oembed_meta = await self._youtube_oembed(search)
            title = oembed_meta.get("title") if oembed_meta else None
            if title is None:
                self.logger.error(f"Failed to extract title via oEmbed for {search}: {e}", exc_info=True)
                raise BotDownloadError(f"Unable to download '{search}'", detail=err_summary) from e

            blocked_err = YouTubeBlockedError(detail=err_summary)
            self.logger.warning(
                f"YouTube download failed for {search}: {err_raw}. Falling back to SoundCloud search for title: {title}"
            )
            query = " ".join(part.strip() for part in title.split("|")[:2])
            try:
                res = await asyncio.to_thread(self.download, f"scsearch:{query[:100]}")
                track = res if isinstance(res, Track) else Track(title=res[0], path=res[1])
                if oembed_meta:
                    if not track.thumbnail and oembed_meta.get("thumbnail_url"):
                        track.thumbnail = oembed_meta.get("thumbnail_url")
                    if not track.uploader and oembed_meta.get("author_name"):
                        track.uploader = oembed_meta.get("author_name")
                    track.url = search
                return track, track.path, True, blocked_err
            except Exception as sc_err:
                sc_msg = getattr(sc_err, "detail", None) or str(sc_err)
                raise BotDownloadError(
                    f"YouTube blocked download ({err_summary}) and SoundCloud search found no match",
                    detail=f"YouTube: {err_summary}\nSoundCloud fallback: {sc_msg}",
                ) from sc_err

    async def _youtube_title(self, url: str):
        meta = await self._youtube_oembed(url)
        return meta.get("title") if meta else None

    async def _youtube_oembed(self, url: str):
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
                    return await resp.json()
        except (aiohttp.ClientError, asyncio.TimeoutError):
            return None
