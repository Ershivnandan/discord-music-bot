import os
import tempfile
from dotenv import load_dotenv

load_dotenv()


class BotConfig:
    DOWNLOAD_DIR = os.path.join(tempfile.gettempdir(), "discord-music")
    DEFAULT_SEARCH_PROVIDER = os.environ.get("DEFAULT_SEARCH_PROVIDER", "ytsearch")
    PROGRESS_UPDATE_INTERVAL = int(os.environ.get("PROGRESS_UPDATE_INTERVAL", "5"))
    KEEP_ALIVE_URL = os.environ.get("KEEP_ALIVE_URL") or os.environ.get("RENDER_EXTERNAL_URL")

    SPEED_FILTERS = {
        1: "-vn",
        2: "-vn -filter:a atempo=2.0",
        3: "-vn -filter:a atempo=2.0,atempo=1.5",
    }

    COMMANDS_MESSAGE = (
        "🎵 **I'm here!** Use the interactive buttons on the player card below, "
        "or these commands:\n\n"
        "`!play <song or URL>` — play a song, or queue it if one is playing\n"
        "`!pause` / `!resume` — pause or resume playback\n"
        "`!next` (or `!skip`) / `!prev` — next or previous song\n"
        "`!speed 1|2|3` — playback speed (1.0x / 2.0x / 3.0x)\n"
        "`!loop [off|track|queue]` — set or cycle repeat mode\n"
        "`!shuffle` — randomize upcoming queue tracks\n"
        "`!queue` (or `!q`) — view upcoming songs\n"
        "`!leave` — stop playback, clear queue and disconnect\n"
        "`!join` — pull bot into your voice channel"
    )

    @classmethod
    def get_ydl_options(cls) -> dict:
        os.makedirs(cls.DOWNLOAD_DIR, exist_ok=True)

        player_clients = ["tv", "web_embedded", "visionos", "mweb", "android_vr"]
        if os.environ.get("YTDLP_PLAYER_CLIENTS"):
            player_clients = [
                client.strip()
                for client in os.environ["YTDLP_PLAYER_CLIENTS"].split(",")
                if client.strip()
            ]

        options = {
            "format": "bestaudio[protocol!*=m3u8]/bestaudio/best",
            "noplaylist": True,
            "quiet": True,
            "default_search": cls.DEFAULT_SEARCH_PROVIDER,
            "outtmpl": os.path.join(cls.DOWNLOAD_DIR, "%(id)s.%(ext)s"),
            "ratelimit": 1_500_000,
            "extractor_args": {
                "youtubepot-bgutilhttp": {
                    "base_url": [os.environ.get("POT_PROVIDER_URL", "http://127.0.0.1:4416")]
                },
                "youtube": {
                    "player_client": player_clients,
                },
            },
        }

        if os.environ.get("YTDLP_PROXY"):
            options["proxy"] = os.environ["YTDLP_PROXY"]

        return options


DOWNLOAD_DIR = BotConfig.DOWNLOAD_DIR
DEFAULT_SEARCH_PROVIDER = BotConfig.DEFAULT_SEARCH_PROVIDER
PROGRESS_UPDATE_INTERVAL = BotConfig.PROGRESS_UPDATE_INTERVAL
SPEED_FILTERS = BotConfig.SPEED_FILTERS
KEEP_ALIVE_URL = BotConfig.KEEP_ALIVE_URL
COMMANDS_MESSAGE = BotConfig.COMMANDS_MESSAGE
YDL_OPTIONS = BotConfig.get_ydl_options()
