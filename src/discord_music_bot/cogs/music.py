"""All user-facing music commands."""

import yt_dlp
from discord.ext import commands

from ..config import COMMANDS_MESSAGE, SPEED_FILTERS
from ..core.downloader import SongDownloader
from ..core.errors import DownloadError, MusicBotError, QueueError, VoiceChannelError, YouTubeBlockedError
from ..core.logger import BotLogger


class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.playback = bot.playback
        self.downloader = SongDownloader()
        self.logger = BotLogger("music_cog")

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        """Global error listener for Music commands, formatting MusicBotError embeds."""
        original = getattr(error, "original", error)

        if isinstance(original, MusicBotError):
            original.log_with(self.logger)
            await ctx.send(embed=original.to_embed())
        elif isinstance(error, (commands.BadArgument, commands.MissingRequiredArgument)):
            err = MusicBotError(f"Invalid command arguments: {error}", code="ERR_BAD_ARGUMENT", guild_id=ctx.guild.id)
            err.log_with(self.logger)
            await ctx.send(embed=err.to_embed())
        elif isinstance(error, commands.CommandNotFound):
            pass  # ignore unknown commands
        else:
            self.logger.error(f"Unhandled command error in '{ctx.command}': {error}", guild_id=ctx.guild.id, exc_info=True)
            err = MusicBotError("An unexpected error occurred while executing the command.", detail=str(error), guild_id=ctx.guild.id)
            await ctx.send(embed=err.to_embed())

    @commands.command(name="join")
    async def join(self, ctx):
        if ctx.author.voice is None:
            raise VoiceChannelError("You need to be in a voice channel first.", guild_id=ctx.guild.id)
        channel = ctx.author.voice.channel
        if ctx.voice_client is None:
            await channel.connect()
            self.logger.info(f"Connected to voice channel: {channel.name}", guild_id=ctx.guild.id)
            await ctx.send(COMMANDS_MESSAGE)
        else:
            await ctx.voice_client.move_to(channel)
            self.logger.info(f"Moved to voice channel: {channel.name}", guild_id=ctx.guild.id)

    @commands.command(name="play")
    async def play(self, ctx, *, search: str):
        self.logger.info(f"Command '!play' invoked by {ctx.author}: '{search}'", guild_id=ctx.guild.id)
        if ctx.voice_client is None:
            if ctx.author.voice is None:
                raise VoiceChannelError("Join a voice channel first.", guild_id=ctx.guild.id)
            await ctx.author.voice.channel.connect()
            self.logger.info(f"Connected to voice channel: {ctx.author.voice.channel.name}", guild_id=ctx.guild.id)
            await ctx.send(COMMANDS_MESSAGE)

        async with ctx.typing():
            title, path, used_fallback, blocked_err = await self.downloader.download_async(search)

        if used_fallback:
            reason = blocked_err.detail if blocked_err and blocked_err.detail else "Bot-check challenge"
            self.logger.warning(
                f"Played SoundCloud fallback '{title}' for requested query '{search}' (Reason: {reason})",
                guild_id=ctx.guild.id,
            )
            await ctx.send(
                f"⚠️ YouTube blocked direct download (`{reason[:120]}`) — playing closest SoundCloud match: **{title}**"
            )

        player = self.playback.get_player(ctx.guild.id)
        player.playlist.append((title, path))
        player.ctx = ctx
        self.logger.info(
            f"Queued track: '{title}' (queue position {len(player.playlist)})",
            guild_id=ctx.guild.id,
        )

        if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
            await self.playback.refresh_player(ctx)  # card shows the updated queue at the bottom
        else:
            await self.playback.play_index(ctx, len(player.playlist) - 1)

    @commands.command(name="next", aliases=["skip"])
    async def next_song(self, ctx):
        self.logger.info(f"Command '!next' invoked by {ctx.author}", guild_id=ctx.guild.id)
        if ctx.voice_client is None:
            return
        player = self.playback.get_player(ctx.guild.id)
        if player.index + 1 < len(player.playlist):
            await self.playback.play_index(ctx, player.index + 1)
        else:
            raise QueueError("No next song in the queue.", guild_id=ctx.guild.id)

    @commands.command(name="prev")
    async def prev_song(self, ctx):
        self.logger.info(f"Command '!prev' invoked by {ctx.author}", guild_id=ctx.guild.id)
        if ctx.voice_client is None:
            return
        player = self.playback.get_player(ctx.guild.id)
        if player.index > 0:
            await self.playback.play_index(ctx, player.index - 1)
        else:
            raise QueueError("No previous song in the queue.", guild_id=ctx.guild.id)

    @commands.command(name="speed")
    async def speed(self, ctx, value: int):
        self.logger.info(f"Command '!speed {value}' invoked by {ctx.author}", guild_id=ctx.guild.id)
        if value not in SPEED_FILTERS:
            raise MusicBotError("Speed can only be 1, 2 or 3 (e.g. `!speed 2`).", code="ERR_INVALID_SPEED", guild_id=ctx.guild.id)
        await self.playback.set_speed(ctx, value)

    @commands.command(name="pause")
    async def pause(self, ctx):
        self.logger.info(f"Command '!pause' invoked by {ctx.author}", guild_id=ctx.guild.id)
        if ctx.voice_client and ctx.voice_client.is_playing():
            await self.playback.pause(ctx)

    @commands.command(name="resume")
    async def resume(self, ctx):
        self.logger.info(f"Command '!resume' invoked by {ctx.author}", guild_id=ctx.guild.id)
        if ctx.voice_client and ctx.voice_client.is_paused():
            await self.playback.resume(ctx)

    @commands.command(name="leave")
    async def leave(self, ctx):
        self.logger.info(f"Command '!leave' invoked by {ctx.author}", guild_id=ctx.guild.id)
        if ctx.voice_client:
            await self.playback.disconnect_and_cleanup(ctx)


