"""All user-facing music commands."""

import yt_dlp
from discord.ext import commands

from ..config import COMMANDS_MESSAGE, SPEED_FILTERS
from ..core.downloader import SongDownloader


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.playback = bot.playback
        self.downloader = SongDownloader()

    @commands.command(name="join")
    async def join(self, ctx):
        if ctx.author.voice is None:
            await ctx.send("You need to be in a voice channel first.")
            return
        channel = ctx.author.voice.channel
        if ctx.voice_client is None:
            await channel.connect()
            await ctx.send(COMMANDS_MESSAGE)
        else:
            await ctx.voice_client.move_to(channel)

    @commands.command(name="play")
    async def play(self, ctx, *, search: str):
        if ctx.voice_client is None:
            if ctx.author.voice is None:
                await ctx.send("Join a voice channel first.")
                return
            await ctx.author.voice.channel.connect()
            await ctx.send(COMMANDS_MESSAGE)

        async with ctx.typing():
            try:
                title, path, used_fallback = await self.downloader.download_async(search)
            except yt_dlp.utils.DownloadError as e:
                await ctx.send(f"Couldn't fetch that song: {str(e)[:200]}")
                return

        if used_fallback:
            await ctx.send(
                f"⚠️ YouTube blocked the download — playing the closest SoundCloud match: **{title}**"
            )

        player = self.playback.get_player(ctx.guild.id)
        player.playlist.append((title, path))
        player.ctx = ctx

        if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
            await self.playback.refresh_player(ctx)  # card shows the updated queue at the bottom
        else:
            await self.playback.play_index(ctx, len(player.playlist) - 1)

    @commands.command(name="next", aliases=["skip"])
    async def next_song(self, ctx):
        if ctx.voice_client is None:
            return
        player = self.playback.get_player(ctx.guild.id)
        if player.index + 1 < len(player.playlist):
            await self.playback.play_index(ctx, player.index + 1)
        else:
            await ctx.send("No next song in the queue.")

    @commands.command(name="prev")
    async def prev_song(self, ctx):
        if ctx.voice_client is None:
            return
        player = self.playback.get_player(ctx.guild.id)
        if player.index > 0:
            await self.playback.play_index(ctx, player.index - 1)
        else:
            await ctx.send("No previous song.")

    @commands.command(name="speed")
    async def speed(self, ctx, value: int):
        if value not in SPEED_FILTERS:
            await ctx.send("Speed can be 1, 2 or 3 (e.g. `!speed 2`).")
            return
        await self.playback.set_speed(ctx, value)

    @speed.error
    async def speed_error(self, ctx, error):
        if isinstance(error, (commands.BadArgument, commands.MissingRequiredArgument)):
            await ctx.send("Usage: `!speed 1`, `!speed 2` or `!speed 3`.")
        else:
            raise error

    @commands.command(name="pause")
    async def pause(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            await self.playback.refresh_player(ctx)

    @commands.command(name="resume")
    async def resume(self, ctx):
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            await self.playback.refresh_player(ctx)

    @commands.command(name="leave")
    async def leave(self, ctx):
        if ctx.voice_client:
            await self.playback.disconnect_and_cleanup(ctx)
