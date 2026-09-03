"""The bot itself: wiring, events, and the keep-alive background task."""

import aiohttp
import discord
from discord.ext import commands, tasks

from .cogs.music import Music
from .config import KEEP_ALIVE_URL
from .core.playback import PlaybackManager


class MusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="!", intents=intents)
        self.playback = PlaybackManager(self)

    async def setup_hook(self):
        await self.add_cog(Music(self))

    async def on_ready(self):
        print(f"Logged in as {self.user}")
        if KEEP_ALIVE_URL and not self.keep_alive.is_running():
            self.keep_alive.start()
            print(f"Keep-alive pings started for {KEEP_ALIVE_URL}")

    @tasks.loop(minutes=5)
    async def keep_alive(self):
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    KEEP_ALIVE_URL, timeout=aiohttp.ClientTimeout(total=30)
                ) as resp:
                    print(f"Keep-alive ping: {resp.status}")
        except Exception as e:
            print(f"Keep-alive ping failed: {e}")
