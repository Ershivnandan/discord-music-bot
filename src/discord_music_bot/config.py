"""Environment and static configuration for the bot."""

import os
import tempfile

from dotenv import load_dotenv

load_dotenv()

# Songs are fully downloaded before playing: streaming over the network on
# Render's tiny free instance causes crackling/lag whenever the connection
# jitters, while playing a local file is rock solid.
DOWNLOAD_DIR = os.path.join(tempfile.gettempdir(), "discord-music")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

YDL_OPTIONS = {
    # Prefer progressive (non-HLS) streams: single small file, fast download
    "format": "bestaudio[protocol!*=m3u8]/bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    # SoundCloud search: unlike YouTube, it doesn't block server IPs
    "default_search": "scsearch",
    "outtmpl": os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s"),
    # Throttle downloads so queueing a song mid-playback doesn't starve the
    # tiny instance's CPU/network and stall the audio thread
    "ratelimit": 1_500_000,
    # PO tokens let YouTube pass the bot-check it gives datacenter IPs.
    # The bgutil sidecar container generates them (see docker-compose.yml).
    "extractor_args": {
        "youtubepot-bgutilhttp": {
            "base_url": [os.environ.get("POT_PROVIDER_URL", "http://127.0.0.1:4416")]
        },
        "youtube": {
            # Bypasses YouTube datacenter IP bot-check ("Sign in to confirm you're not a bot").
            # Unauthenticated "web" client triggers hard BotGuard blocks on datacenter IPs;
            # visionos and mweb with GVS PO tokens fetch audio without bot challenges.
            "player_client": ["visionos", "mweb", "android_vr"]
        }
    },
}

# Optional proxy support (e.g. SOCKS5, HTTP, or Cloudflare WARP proxy)
if os.environ.get("YTDLP_PROXY"):
    YDL_OPTIONS["proxy"] = os.environ["YTDLP_PROXY"]

# If a Netscape cookiefile is provided, we can safely use authenticated web clients.
_cookies_candidates = [
    os.environ.get("YTDLP_COOKIES_FILE"),
    os.path.join(os.getcwd(), "cookies.txt"),
    "/app/cookies.txt",
]
for _candidate in _cookies_candidates:
    if _candidate and os.path.isfile(_candidate):
        YDL_OPTIONS["cookiefile"] = _candidate
        YDL_OPTIONS["extractor_args"]["youtube"]["player_client"] = [
            "web",
            "mweb",
            "web_music",
            "visionos",
        ]
        break


# ffmpeg's atempo filter caps at 2.0 per stage, so 3x chains two stages
SPEED_FILTERS = {
    1: "-vn",
    2: "-vn -filter:a atempo=2.0",
    3: "-vn -filter:a atempo=2.0,atempo=1.5",
}

# Render sets RENDER_EXTERNAL_URL automatically; pinging our own public URL
# counts as inbound traffic, so the free instance never spins down.
KEEP_ALIVE_URL = os.environ.get("KEEP_ALIVE_URL") or os.environ.get("RENDER_EXTERNAL_URL")

COMMANDS_MESSAGE = (
    "🎵 **I'm here!** Use the buttons on the player card below, "
    "or these commands:\n\n"
    "`!play <song or URL>` — play a song, or queue it if one is playing\n"
    "`!next` (or `!skip`) / `!prev` — next / previous song\n"
    "`!speed 1|2|3` — playback speed (1x / 2x / 3x)\n"
    "`!pause` / `!resume` — pause / resume playback\n"
    "`!leave` — clear the queue and disconnect\n"
    "`!join` — pull me into your voice channel"
)
