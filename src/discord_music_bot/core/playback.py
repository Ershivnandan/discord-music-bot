"""Per-guild playback state and the manager that drives playback."""

import asyncio
import os

import discord

from ..config import SPEED_FILTERS
from ..ui.player_card import PlayerView, build_embed


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
        source = discord.FFmpegOpusAudio(path, options=SPEED_FILTERS[player.speed])

        def after_playing(error):
            if error:
                print(f"Playback error: {error}")
            if generation != player.generation:
                return  # superseded by a manual next/prev/speed restart
            fut = asyncio.run_coroutine_threadsafe(self.advance(ctx), self.bot.loop)
            try:
                fut.result()
            except Exception as e:
                print(e)

        voice.play(source, after=after_playing)
        player.ctx = ctx
        await self.refresh_player(ctx)

    async def advance(self, ctx):
        player = self.get_player(ctx.guild.id)
        if player.index + 1 < len(player.playlist):
            await self.play_index(ctx, player.index + 1)
        else:
            await self.refresh_player(ctx)  # end of queue: show idle state on the card

    async def set_speed(self, ctx, value: int):
        player = self.get_player(ctx.guild.id)
        if player.speed != value:
            player.speed = value
            voice = ctx.guild.voice_client
            if voice and (voice.is_playing() or voice.is_paused()):
                # restart the current song at the new speed
                await self.play_index(ctx, player.index)
                return
        await self.refresh_player(ctx)

    async def disconnect_and_cleanup(self, ctx):
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
                except OSError:
                    pass
        voice = ctx.guild.voice_client
        if voice:
            await voice.disconnect()
