"""Per-guild playback state and the manager that drives playback."""

import asyncio
import os

import discord

from ..config import SPEED_FILTERS
from ..ui.player_card import PlayerView, build_embed
from .errors import PlaybackError, QueueError
from .logger import BotLogger



class GuildPlayer:
    """Per-guild playback state: full session playlist + current position."""

    def __init__(self):
        self.playlist = []  # list of (title, file path); kept for !prev
        self.index = -1  # position of the currently playing song
        self.speed = 1
        # Bumped on every (re)start; stale after-callbacks see a mismatch
        # and skip auto-advancing, so manual next/prev/speed don't double-play
        self.generation = 0
        self.message = None  # the player-card message with the buttons
        self.ctx = None  # last command context, used by button callbacks


class PlaybackManager:
    """Owns every guild's player state and controls what is playing."""

    def __init__(self, bot):
        self.bot = bot
        self.players = {}  # guild_id -> GuildPlayer
        self.logger = BotLogger("playback")


    def get_player(self, guild_id) -> GuildPlayer:
        return self.players.setdefault(guild_id, GuildPlayer())

    async def refresh_player(self, ctx):
        """Render the player card as the newest message in the channel.

        If the card is already the last message, edit it in place; otherwise
        delete it and re-send at the bottom so the buttons never get buried
        under queued-song chatter.
        """
        player = self.get_player(ctx.guild.id)
        embed = build_embed(player, ctx.guild)
        view = PlayerView(self, ctx.guild.id)
        message = player.message
        channel = ctx.channel
        if message and message.channel.id == channel.id and channel.last_message_id == message.id:
            try:
                await message.edit(embed=embed, view=view)
                return
            except discord.HTTPException:
                pass
        if message:
            try:
                await message.delete()
            except discord.HTTPException:
                pass
        player.message = await channel.send(embed=embed, view=view)

    async def play_index(self, ctx, index: int):
        """Start playing playlist[index], stopping whatever is on now."""
        player = self.get_player(ctx.guild.id)
        if not 0 <= index < len(player.playlist):
            return
        player.index = index
        player.generation += 1
        generation = player.generation

        voice = ctx.voice_client
        if voice.is_playing() or voice.is_paused():
            voice.stop()

        title, path = player.playlist[index]
        self.logger.info(
            f"Starting playback: track {index + 1}/{len(player.playlist)}: '{title}' at {player.speed}x speed",
            guild_id=ctx.guild.id,
        )
        source = discord.FFmpegOpusAudio(path, options=SPEED_FILTERS[player.speed])

        def after_playing(error):
            if error:
                pb_err = PlaybackError("Audio stream error occurred during playback", detail=str(error), guild_id=ctx.guild.id)
                pb_err.log_with(self.logger)
            if generation != player.generation:
                self.logger.debug(
                    f"Skipping stale after_playing callback (generation {generation} vs {player.generation})",
                    guild_id=ctx.guild.id,
                )
                return  # superseded by a manual next/prev/speed restart
            fut = asyncio.run_coroutine_threadsafe(self.advance(ctx), self.bot.loop)
            try:
                fut.result()
            except Exception as e:
                advance_err = PlaybackError("Error during auto-advance to next track", detail=str(e), guild_id=ctx.guild.id)
                advance_err.log_with(self.logger)


        voice.play(source, after=after_playing)
        player.ctx = ctx
        await self.refresh_player(ctx)

    async def advance(self, ctx):
        player = self.get_player(ctx.guild.id)
        if player.index + 1 < len(player.playlist):
            self.logger.info(f"Advancing to next track (index {player.index + 1})", guild_id=ctx.guild.id)
            await self.play_index(ctx, player.index + 1)
        else:
            self.logger.info("Reached end of queue. Player is now idle.", guild_id=ctx.guild.id)
            await self.refresh_player(ctx)  # end of queue: show idle state on the card

    async def set_speed(self, ctx, value: int):
        player = self.get_player(ctx.guild.id)
        if player.speed != value:
            self.logger.info(f"Playback speed changed from {player.speed}x to {value}x", guild_id=ctx.guild.id)
            player.speed = value
            voice = ctx.guild.voice_client
            if voice and (voice.is_playing() or voice.is_paused()):
                # restart the current song at the new speed
                await self.play_index(ctx, player.index)
                return
        await self.refresh_player(ctx)

    async def disconnect_and_cleanup(self, ctx):
        self.logger.info("Disconnecting from voice and cleaning up playlist cache.", guild_id=ctx.guild.id)
        player = self.players.pop(ctx.guild.id, None)
        if player:
            player.generation += 1  # cancel any pending auto-advance
            if player.message:
                try:
                    await player.message.delete()
                except discord.HTTPException:
                    pass
            for _, path in player.playlist:
                try:
                    os.remove(path)
                    self.logger.debug(f"Removed temp file: {path}", guild_id=ctx.guild.id)
                except OSError as e:
                    self.logger.warning(f"Could not remove temp file {path}: {e}", guild_id=ctx.guild.id)
        voice = ctx.guild.voice_client
        if voice:
            await voice.disconnect()
            self.logger.info("Voice connection closed.", guild_id=ctx.guild.id)

