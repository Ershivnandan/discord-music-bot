import asyncio
import re
import urllib.parse
from dataclasses import dataclass
from typing import Optional

import aiohttp
import yt_dlp

from ..config import YDL_OPTIONS
from .errors import DownloadError as BotDownloadError, YouTubeBlockedError
from .logger import BotLogger


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
    YOUTUBE_URL_RE = re.compile(r"https?://(?:www\.|m\.|music\.)?(?:youtube\.com|youtu\.be)/")
    TAG_PATTERN = re.compile(
        r"[\(\[\{]"
        r"(?:official\s+(?:music\s+)?video|official\s+audio|official|lyrics?|lyric\s+video|"
        r"audio|visualizer|hd|4k|remastered|full\s+song|video\s+song|video|music\s+video|"
        r"prod\.?[^\)\]\}]+)"
        r"[\)\]\}]",
        re.IGNORECASE,
    )

    def __init__(self, options: Optional[dict] = None):
        self.options = options or YDL_OPTIONS
        self.logger = BotLogger("downloader")

    @classmethod
    def generate_search_candidates(cls, title: str) -> list[str]:
        candidates: list[str] = []

        primary = re.split(r"[\s]*[|•//~][\s]*", title)[0].strip()
        cleaned_primary = cls.TAG_PATTERN.sub("", primary).strip()
        cleaned_primary = re.sub(r"\s+", " ", cleaned_primary).strip(" -:")

        if cleaned_primary and cleaned_primary not in candidates:
            candidates.append(cleaned_primary)

        if " - " in cleaned_primary:
            without_hyphen = re.sub(r"\s+", " ", cleaned_primary.replace(" - ", " ")).strip()
            if without_hyphen and without_hyphen not in candidates:
                candidates.append(without_hyphen)
            parts = cleaned_primary.split(" - ")
            if len(parts) == 2:
                p0, p1 = parts[0].strip(), parts[1].strip()
                if p0 and len(p0) > 2 and p0 not in candidates:
                    candidates.append(p0)
                if p1 and len(p1) > 2 and p1 not in candidates:
                    candidates.append(p1)

        cleaned_full = cls.TAG_PATTERN.sub("", title).strip()
        cleaned_full = re.sub(r"\s+", " ", cleaned_full).strip(" -:")
        if cleaned_full and cleaned_full not in candidates:
            candidates.append(cleaned_full)

        old_query = " ".join(part.strip() for part in title.split("|")[:2]).strip()
        if old_query and old_query not in candidates:
            candidates.append(old_query)

        if title and title not in candidates:
            candidates.append(title)

        return candidates

    @staticmethod
    def clean_error_summary(error: Exception) -> str:
        err_raw = str(error).strip()
        err_lines = [line.strip() for line in err_raw.splitlines() if line.strip()]
        err_summary = err_lines[-1] if err_lines else err_raw
        if "ERROR: [youtube]" in err_summary:
            err_summary = err_summary.split("ERROR: [youtube]")[-1].strip(": ")
        return err_summary

    def download(self, search: str) -> Track:
        self.logger.info(f"Starting download for query/URL: {search}")
        try:
            with yt_dlp.YoutubeDL(self.options) as ydl:
                info = ydl.extract_info(search, download=True)
                if not info:
                    raise BotDownloadError(f"No stream found for: {search}")
                if "entries" in info:
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
        except (yt_dlp.utils.DownloadError, BotDownloadError):
            raise
        except Exception as e:
            raise BotDownloadError(f"Failed while downloading: {search}", detail=str(e)) from e

    async def _search_soundcloud_candidates(self, candidates: list[str]) -> Track:
        last_err = None
        for cand in candidates:
            cand_clean = cand.strip()
            if not cand_clean:
                continue
            sc_query = f"scsearch:{cand_clean[:100]}"
            self.logger.info(f"Attempting SoundCloud fallback query: {sc_query}")
            try:
                res = await asyncio.to_thread(self.download, sc_query)
                return res if isinstance(res, Track) else Track(title=res[0], path=res[1])
            except Exception as err:
                last_err = err
                self.logger.warning(f"SoundCloud search for '{cand_clean}' failed: {err}")
        if last_err:
            raise last_err
        raise BotDownloadError("SoundCloud search found no match for any candidate query")

    async def download_async(self, search: str):
        is_url = search.startswith(("http://", "https://"))
        is_explicit_extractor = any(
            search.startswith(p) for p in ("scsearch:", "ytsearch:", "ytsearch1:", "gvsearch:")
        )

        if not is_url and not is_explicit_extractor:
            yt_query = f"ytsearch1:{search}"
            try:
                res = await asyncio.to_thread(self.download, yt_query)
                track = res if isinstance(res, Track) else Track(title=res[0], path=res[1])
                return track, track.path, False, None
            except (yt_dlp.utils.DownloadError, BotDownloadError) as e:
                err_summary = self.clean_error_summary(e)
                blocked_err = YouTubeBlockedError(detail=err_summary)
                self.logger.warning(
                    f"YouTube search failed for '{search}': {e}. Falling back to SoundCloud search."
                )
                sc_query = f"scsearch:{search[:100]}"
                try:
                    res = await asyncio.to_thread(self.download, sc_query)
                    track = res if isinstance(res, Track) else Track(title=res[0], path=res[1])
                    return track, track.path, True, blocked_err
                except Exception as sc_err:
                    alt_candidates = [
                        c for c in self.generate_search_candidates(search)
                        if c.lower() != search.lower()
                    ]
                    if alt_candidates:
                        try:
                            track = await self._search_soundcloud_candidates(alt_candidates)
                            return track, track.path, True, blocked_err
                        except Exception:
                            pass
                    sc_msg = getattr(sc_err, "detail", None) or str(sc_err)
                    raise BotDownloadError(
                        f"YouTube search failed ({err_summary}) and SoundCloud search found no match",
                        detail=f"YouTube: {err_summary}\nSoundCloud fallback: {sc_msg}",
                    ) from sc_err

        try:
            res = await asyncio.to_thread(self.download, search)
            track = res if isinstance(res, Track) else Track(title=res[0], path=res[1])
            return track, track.path, False, None
        except yt_dlp.utils.DownloadError as e:
            err_summary = self.clean_error_summary(e)
            oembed_meta = await self._youtube_oembed(search)
            title = oembed_meta.get("title") if oembed_meta else None
            if title is None:
                self.logger.error(f"Failed to extract title via oEmbed for {search}: {e}", exc_info=True)
                raise BotDownloadError(f"Unable to download '{search}'", detail=err_summary) from e

            blocked_err = YouTubeBlockedError(detail=err_summary)
            self.logger.warning(
                f"YouTube download failed for {search}: {e}. Falling back to SoundCloud search for title: {title}"
            )
            candidates = self.generate_search_candidates(title)
            try:
                track = await self._search_soundcloud_candidates(candidates)
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

    async def _youtube_title(self, url: str) -> Optional[str]:
        meta = await self._youtube_oembed(url)
        return meta.get("title") if meta else None

    async def _youtube_oembed(self, url: str) -> Optional[dict]:
        if not self.YOUTUBE_URL_RE.match(url):
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


generate_search_candidates = SongDownloader.generate_search_candidates
YOUTUBE_URL_RE = SongDownloader.YOUTUBE_URL_RE
