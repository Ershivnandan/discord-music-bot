"""Entry point for the discord-music-bot script."""

import os

from .bot import MusicBot
from .core.audio_patch import patch_audio_player
from .core.logger import BotLogger
from .web.health import HealthServer


def main() -> None:
    BotLogger.setup()
    logger = BotLogger("main")
    logger.info("Initializing Discord Music Bot...")

    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        logger.error("DISCORD_TOKEN environment variable is not set.")
        raise SystemExit("DISCORD_TOKEN environment variable is not set.")
    patch_audio_player()
    bot = MusicBot()
    HealthServer(bot=bot).start()
    bot.run(token)

