import asyncio
import os
import random
import time
from typing import Optional

import discord

from ..config import PROGRESS_UPDATE_INTERVAL, SPEED_FILTERS
from ..ui.player_card import PlayerView, build_embed
from .errors import PlaybackError
from .logger import BotLogger


class GuildPlayer:
    def __init__(self):
        self.playlist = []
        self.index = -1
        self.speed = 1
        self.generation = 0
        self.message = None
        self.ctx = None
        self.position = 0.0
        self.play_start_time = None
        self.is_paused = False
        self.loop_mode = "off"
        self.progress_task: Optional[asyncio.Task] = None

    def cancel_progress_task(self):
        if self.progress_task and not self.progress_task.done():
            self.progress_task.cancel()
        self.progress_task = None

    def get_current_position(self) -> float:
        pos = self.position
        if not self.is_paused and self.play_start_time is not None:
            elapsed = time.monotonic() - self.play_start_time
            pos += elapsed * self.speed
        return max(0.0, pos)

    def pause(self):
        if not self.is_paused:
            self.position = self.get_current_position()
            self.is_paused = True
            self.play_start_time = None

    def resume(self):
        if self.is_paused:
            self.is_paused = False
            self.play_start_time = time.monotonic()


class PlaybackManager:
    def __init__(self, bot):
        self.bot = bot
        self.players = {}
        self.logger = BotLogger("playback")

    def get_player(self, guild_id) -> GuildPlayer:
        return self.players.setdefault(guild_id, GuildPlayer())

    async def refresh_player(self, ctx):
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

    async def _progress_updater(self, ctx, player: GuildPlayer, generation: int):
        try:
            while generation == player.generation:
                await asyncio.sleep(PROGRESS_UPDATE_INTERVAL)
                if generation != player.generation:
                    break

                voice = ctx.voice_client or (ctx.guild.voice_client if ctx.guild else None)
                if not voice or not voice.is_connected():
                    break
                if not voice.is_playing():
                    continue
                if not player.message:
                    continue

                try:
                    embed = build_embed(player, ctx.guild)
                    await player.message.edit(embed=embed)
                except discord.NotFound:
                    player.message = None
                    break
                except discord.HTTPException as e:
                    if getattr(e, "status", None) == 429:
                        retry_after = 5.0
                        if hasattr(e, "response") and hasattr(e.response, "headers"):
                            retry_after = float(e.response.headers.get("Retry-After", 5.0))
                        await asyncio.sleep(retry_after)
                    else:
                        self.logger.debug(f"HTTPException in progress updater: {e}", guild_id=ctx.guild.id)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.logger.debug(f"Unexpected error in progress updater: {e}", guild_id=ctx.guild.id)

    async def play_index(self, ctx, index: int, start_time: float = 0.0):
        player = self.get_player(ctx.guild.id)
        if not 0 <= index < len(player.playlist):
            return
        player.cancel_progress_task()
        player.index = index
        player.generation += 1
        generation = player.generation

        voice = ctx.voice_client or (ctx.guild.voice_client if ctx.guild else None)
        if voice and (voice.is_playing() or voice.is_paused()):
            voice.stop()

        title, path = player.playlist[index]
        player.position = max(0.0, float(start_time))
        player.play_start_time = time.monotonic()
        player.is_paused = False

        self.logger.info(
            f"Starting playback: track {index + 1}/{len(player.playlist)}: '{title}' at {player.speed}x speed "
            f"from timestamp {player.position:.2f}s",
            guild_id=ctx.guild.id,
        )
        before_options = f"-ss {player.position:.2f}" if player.position > 0.0 else None
        source = discord.FFmpegOpusAudio(
            path,
            before_options=before_options,
            options=SPEED_FILTERS[player.speed],
        )

        def after_playing(error):
            if error:
                pb_err = PlaybackError("Audio stream error occurred during playback", detail=str(error), guild_id=ctx.guild.id)
                pb_err.log_with(self.logger)
            if generation != player.generation:
                self.logger.debug(
                    f"Skipping stale after_playing callback (generation {generation} vs {player.generation})",
                    guild_id=ctx.guild.id,
                )
                return
            fut = asyncio.run_coroutine_threadsafe(self.advance(ctx), self.bot.loop)
            try:
                fut.result()
            except Exception as e:
                advance_err = PlaybackError("Error during auto-advance to next track", detail=str(e), guild_id=ctx.guild.id)
                advance_err.log_with(self.logger)

        voice.play(source, after=after_playing)
        player.ctx = ctx
        await self.refresh_player(ctx)
        try:
            player.progress_task = asyncio.create_task(
                self._progress_updater(ctx, player, generation)
            )
        except RuntimeError:
            pass

    async def advance(self, ctx):
        player = self.get_player(ctx.guild.id)
        if not player.playlist:
            return

        if player.loop_mode == "track" and 0 <= player.index < len(player.playlist):
            self.logger.info(f"Repeating current track (loop: track, index {player.index})", guild_id=ctx.guild.id)
            await self.play_index(ctx, player.index)
            return

        if player.index + 1 < len(player.playlist):
            self.logger.info(f"Advancing to next track (index {player.index + 1})", guild_id=ctx.guild.id)
            await self.play_index(ctx, player.index + 1)
        elif player.loop_mode == "queue" and len(player.playlist) > 0:
            self.logger.info("Looping queue back to track 1 (loop: queue)", guild_id=ctx.guild.id)
            await self.play_index(ctx, 0)
        else:
            player.cancel_progress_task()
            self.logger.info("Reached end of queue. Player is now idle.", guild_id=ctx.guild.id)
            await self.refresh_player(ctx)

    def shuffle(self, guild_id) -> bool:
        player = self.get_player(guild_id)
        unplayed = player.playlist[player.index + 1 :]
        if len(unplayed) <= 1:
            return False
        random.shuffle(unplayed)
        player.playlist[player.index + 1 :] = unplayed
        self.logger.info(f"Shuffled {len(unplayed)} upcoming tracks in queue", guild_id=guild_id)
        return True

    async def pause(self, ctx):
        player = self.get_player(ctx.guild.id)
        voice = ctx.voice_client or (ctx.guild.voice_client if ctx.guild else None)
        if voice and voice.is_playing():
            player.cancel_progress_task()
            player.pause()
            voice.pause()
            self.logger.info(f"Playback paused at timestamp {player.position:.2f}s", guild_id=ctx.guild.id)
            await self.refresh_player(ctx)

    async def resume(self, ctx):
        player = self.get_player(ctx.guild.id)
        voice = ctx.voice_client or (ctx.guild.voice_client if ctx.guild else None)
        if voice and voice.is_paused():
            player.resume()
            voice.resume()
            self.logger.info(f"Playback resumed from timestamp {player.position:.2f}s", guild_id=ctx.guild.id)
            await self.refresh_player(ctx)
            try:
                player.cancel_progress_task()
                player.progress_task = asyncio.create_task(
                    self._progress_updater(ctx, player, player.generation)
                )
            except RuntimeError:
                pass

    async def set_speed(self, ctx, value: int):
        player = self.get_player(ctx.guild.id)
        if player.speed != value:
            current_pos = player.get_current_position()
            self.logger.info(
                f"Playback speed changed from {player.speed}x to {value}x at timestamp {current_pos:.2f}s",
                guild_id=ctx.guild.id,
            )
            player.speed = value
            voice = ctx.voice_client or (ctx.guild.voice_client if ctx.guild else None)
            if voice and (voice.is_playing() or voice.is_paused()):
                was_paused = voice.is_paused()
                await self.play_index(ctx, player.index, start_time=current_pos)
                if was_paused and voice and voice.is_playing():
                    voice.pause()
                    player.pause()
                return
        await self.refresh_player(ctx)

    async def disconnect_and_cleanup(self, ctx):
        self.logger.info("Disconnecting from voice and cleaning up playlist cache.", guild_id=ctx.guild.id)
        player = self.players.pop(ctx.guild.id, None)
        if player:
            player.cancel_progress_task()
            player.generation += 1
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
