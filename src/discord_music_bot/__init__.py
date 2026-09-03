"""Entry point for the discord-music-bot script."""

import os

from .bot import MusicBot
from .core.audio_patch import patch_audio_player
from .web.health import HealthServer


def main() -> None:
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise SystemExit("DISCORD_TOKEN environment variable is not set.")
    patch_audio_player()
    HealthServer().start()
    MusicBot().run(token)
