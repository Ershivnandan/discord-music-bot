"""Song downloads via yt-dlp."""

import asyncio

import yt_dlp

from ..config import YDL_OPTIONS


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
        # yt-dlp is blocking; run it off the event loop
        return await asyncio.to_thread(self.download, search)
