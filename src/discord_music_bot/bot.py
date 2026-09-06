"""The bot itself: wiring, events, and the keep-alive background task."""

import aiohttp
import discord
from discord.ext import commands, tasks

from .cogs.music import Music
from .config import KEEP_ALIVE_URL
from .core.logger import BotLogger
from .core.playback import PlaybackManager


class MusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.logger = BotLogger("bot")
        self.playback = PlaybackManager(self)

    async def setup_hook(self):
        await self.add_cog(Music(self))
        self.logger.info("Music cog loaded successfully.")

    async def on_ready(self):
        self.logger.info(f"Logged in as {self.user} (ID: {self.user.id if self.user else 'unknown'})")
        if KEEP_ALIVE_URL and not self.keep_alive.is_running():
            self.keep_alive.start()
            self.logger.info(f"Keep-alive pings started for {KEEP_ALIVE_URL}")

    @tasks.loop(minutes=5)
    async def keep_alive(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    KEEP_ALIVE_URL, timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    self.logger.info(f"Keep-alive ping status: {resp.status}")
        except Exception as e:
            self.logger.warning(f"Keep-alive ping failed: {e}")

