"""The player-card embed and its button controls."""

import discord


def build_embed(player, guild) -> discord.Embed:
    voice = guild.voice_client
    if 0 <= player.index < len(player.playlist):
        title = player.playlist[player.index][0]
    else:
        title = "Nothing yet — use `!play <song>`"
    if voice and voice.is_paused():
        status = "⏸ Paused"
    elif voice and voice.is_playing():
        status = "▶ Playing"
    else:
        status = "⏹ Idle"
    embed = discord.Embed(title=f"🎵 {title}", color=0x5865F2)
    embed.add_field(name="Status", value=status, inline=True)
    embed.add_field(name="Speed", value=f"{player.speed}x", inline=True)
    if player.playlist:
        embed.add_field(
            name="Song", value=f"{player.index + 1} / {len(player.playlist)}", inline=True
        )
    if player.index + 1 < len(player.playlist):
        embed.add_field(name="Up next", value=player.playlist[player.index + 1][0], inline=False)
    return embed


class PlayerView(discord.ui.View):
    def __init__(self, playback, guild_id):
        super().__init__(timeout=None)
        self.playback = playback  # the PlaybackManager
        self.guild_id = guild_id
        speed = playback.get_player(guild_id).speed
        for child in self.children:
            if child.custom_id and child.custom_id.startswith("speed_"):
                child.style = (
                    discord.ButtonStyle.primary
                    if int(child.custom_id.removeprefix("speed_")) == speed
                    else discord.ButtonStyle.secondary
                )

    async def _player_ctx(self, interaction):
        """Common guard: playback state must exist and the bot be in voice."""
        player = self.playback.get_player(self.guild_id)
        if player.ctx is None or interaction.guild.voice_client is None:
            await interaction.response.send_message(
                "Nothing is playing — use `!play <song>` first.", ephemeral=True
            )
            return None, None
        return player, player.ctx

    @discord.ui.button(emoji="⏮", style=discord.ButtonStyle.secondary, custom_id="prev", row=0)
    async def prev_button(self, interaction, button):
        player, ctx = await self._player_ctx(interaction)
        if player is None:
            return
        if player.index > 0:
            await interaction.response.defer()
            await self.playback.play_index(ctx, player.index - 1)
        else:
            await interaction.response.send_message("No previous song.", ephemeral=True)

    @discord.ui.button(emoji="⏯", style=discord.ButtonStyle.secondary, custom_id="pause", row=0)
    async def pause_button(self, interaction, button):
        player, ctx = await self._player_ctx(interaction)
        if player is None:
            return
        await interaction.response.defer()
        voice = ctx.guild.voice_client
        if voice.is_paused():
            voice.resume()
        elif voice.is_playing():
            voice.pause()
        await self.playback.refresh_player(ctx)

    @discord.ui.button(emoji="⏭", style=discord.ButtonStyle.secondary, custom_id="next", row=0)
    async def next_button(self, interaction, button):
        player, ctx = await self._player_ctx(interaction)
        if player is None:
            return
        if player.index + 1 < len(player.playlist):
            await interaction.response.defer()
            await self.playback.play_index(ctx, player.index + 1)
        else:
            await interaction.response.send_message("No next song in the queue.", ephemeral=True)

    @discord.ui.button(emoji="⏹", style=discord.ButtonStyle.danger, custom_id="stop", row=0)
    async def stop_button(self, interaction, button):
        player, ctx = await self._player_ctx(interaction)
        if player is None:
            return
        await interaction.response.defer()
        await self.playback.disconnect_and_cleanup(ctx)

    @discord.ui.button(label="1x", custom_id="speed_1", row=1)
    async def speed1_button(self, interaction, button):
        await self._set_speed(interaction, 1)

    @discord.ui.button(label="2x", custom_id="speed_2", row=1)
    async def speed2_button(self, interaction, button):
        await self._set_speed(interaction, 2)

    @discord.ui.button(label="3x", custom_id="speed_3", row=1)
    async def speed3_button(self, interaction, button):
        await self._set_speed(interaction, 3)

    async def _set_speed(self, interaction, value):
        player, ctx = await self._player_ctx(interaction)
        if player is None:
            return
        await interaction.response.defer()
        await self.playback.set_speed(ctx, value)
