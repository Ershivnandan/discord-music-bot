"""The rich, interactive player-card embed and its button controls."""

from typing import Optional

import discord


def format_duration(seconds: Optional[float]) -> str:
    """Format seconds into HH:MM:SS or MM:SS format."""
    if seconds is None or seconds < 0:
        return "00:00"
    s = int(seconds)
    hours = s // 3600
    minutes = (s % 3600) // 60
    secs = s % 60
    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def make_progress_bar(current_sec: float, total_sec: Optional[float], length: int = 14) -> str:
    """Renders a sleek Spotify/Discord styled progress bar."""
    curr_str = format_duration(current_sec)
    if total_sec is None or total_sec <= 0:
        return f"`{curr_str} / --:--` 🔘─────────────"

    total_str = format_duration(total_sec)
    progress = max(0.0, min(1.0, current_sec / total_sec))
    index = min(length - 1, max(0, int(progress * length)))
    bar = "━" * index + "🔘" + "─" * (length - 1 - index)
    return f"`{curr_str}` {bar} `{total_str}`"


def build_embed(player, guild) -> discord.Embed:
    """Build a professional, modern Discord player card embed."""
    voice = guild.voice_client if guild else None
    current_pos = player.get_current_position()

    # Determine status badge & dynamic theme color
    if voice and voice.is_paused():
        color = 0xFEE75C  # Warm Amber / Gold
        status_badge = f"⏸️ **Paused ({format_duration(current_pos)})**"
    elif voice and voice.is_playing():
        color = 0x2ECC71  # Vibrant Emerald
        status_badge = "▶️ **Playing**"
    else:
        color = 0x2B2D31  # Charcoal / Idle
        status_badge = "⏹️ **Idle**"

    # Handle empty queue or idle state
    if not (0 <= player.index < len(player.playlist)):
        embed = discord.Embed(
            title="🎵 Discord Music Player",
            description="No track is currently playing.\nUse `!play <song name or URL>` to start listening!",
            color=color,
        )
        embed.add_field(name="📊 Status", value=status_badge, inline=True)
        embed.add_field(name="⚡ Speed", value=f"**{player.speed}.0x**", inline=True)
        loop_name = getattr(player, "loop_mode", "off").capitalize()
        embed.add_field(name="🔁 Loop", value=f"**{loop_name}**", inline=True)
        embed.set_footer(text="discord-music-bot • Low-Latency Audio Engine")
        return embed

    # Extract track metadata (supports Track objects or fallback 2-tuples)
    item = player.playlist[player.index]
    title = getattr(item, "title", None) or (item[0] if isinstance(item, (tuple, list)) else str(item))
    duration = getattr(item, "duration", None)
    thumbnail = getattr(item, "thumbnail", None)
    uploader = getattr(item, "uploader", None)
    url = getattr(item, "url", None)
    requester = getattr(item, "requester", None)

    embed = discord.Embed(color=color)

    # Author header with server/guild branding
    guild_icon = guild.icon.url if (guild and guild.icon) else None
    embed.set_author(name="Now Playing", icon_url=guild_icon)

    # Description: song title link, artist badge, requester, and progress bar
    desc_lines = []
    if url:
        desc_lines.append(f"### 🎵 [{title}]({url})")
    else:
        desc_lines.append(f"### 🎵 {title}")

    sub_badges = []
    if uploader:
        sub_badges.append(f"👤 `{uploader}`")
    if requester:
        sub_badges.append(f"🎧 `Requested by {requester}`")
    if sub_badges:
        desc_lines.append(" • ".join(sub_badges))

    desc_lines.append("")
    desc_lines.append(make_progress_bar(current_pos, duration))
    embed.description = "\n".join(desc_lines)

    # Status badges
    embed.add_field(name="📊 Status", value=status_badge, inline=True)
    embed.add_field(name="⚡ Speed", value=f"**{player.speed}.0x**", inline=True)

    loop_mode = getattr(player, "loop_mode", "off")
    if loop_mode == "track":
        loop_display = "🔂 **Track**"
    elif loop_mode == "queue":
        loop_display = "🔁 **Queue**"
    else:
        loop_display = "**Off**"
    embed.add_field(name="🔁 Loop", value=loop_display, inline=True)
    embed.add_field(name="📑 Queue", value=f"**{player.index + 1} / {len(player.playlist)}**", inline=True)

    # Next track / Up Next preview
    if player.index + 1 < len(player.playlist):
        next_item = player.playlist[player.index + 1]
        next_title = getattr(next_item, "title", None) or (next_item[0] if isinstance(next_item, (tuple, list)) else str(next_item))
        next_url = getattr(next_item, "url", None)
        next_md = f"[{next_title}]({next_url})" if next_url else f"**{next_title}**"
        embed.add_field(name="⏭️ Up Next", value=f"`{player.index + 2}.` {next_md}", inline=False)
    elif loop_mode == "track":
        embed.add_field(name="🔂 Repeat", value="Repeating current track upon completion", inline=False)
    elif loop_mode == "queue" and len(player.playlist) > 1:
        first_item = player.playlist[0]
        first_title = getattr(first_item, "title", None) or (first_item[0] if isinstance(first_item, (tuple, list)) else str(first_item))
        first_url = getattr(first_item, "url", None)
        first_md = f"[{first_title}]({first_url})" if first_url else f"**{first_title}**"
        embed.add_field(name="🔁 Loop Queue", value=f"Loops back to `1.` {first_md}", inline=False)

    # High-resolution thumbnail artwork
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)

    embed.set_footer(text="discord-music-bot • Use buttons below to control playback")
    return embed


class PlayerView(discord.ui.View):
    def __init__(self, playback, guild_id):
        super().__init__(timeout=None)
        self.playback = playback
        self.guild_id = guild_id
        player = playback.get_player(guild_id)
        voice = None
        if player.ctx and player.ctx.guild:
            voice = player.ctx.guild.voice_client

        # Configure button states dynamically
        self.prev_button.disabled = (player.index <= 0)
        loop_mode = getattr(player, "loop_mode", "off")
        self.next_button.disabled = (player.index + 1 >= len(player.playlist) and loop_mode != "queue")

        # Pause / Resume button styling
        if voice and voice.is_paused():
            self.pause_button.label = "Resume"
            self.pause_button.emoji = "▶️"
            self.pause_button.style = discord.ButtonStyle.success
        else:
            self.pause_button.label = "Pause"
            self.pause_button.emoji = "⏸️"
            self.pause_button.style = discord.ButtonStyle.secondary

        # Speed buttons styling
        self.speed1_button.style = (
            discord.ButtonStyle.primary if player.speed == 1 else discord.ButtonStyle.secondary
        )
        self.speed2_button.style = (
            discord.ButtonStyle.primary if player.speed == 2 else discord.ButtonStyle.secondary
        )
        self.speed3_button.style = (
            discord.ButtonStyle.primary if player.speed == 3 else discord.ButtonStyle.secondary
        )

        # Loop button styling
        if loop_mode == "track":
            self.loop_button.label = "Loop: Track"
            self.loop_button.emoji = "🔂"
            self.loop_button.style = discord.ButtonStyle.primary
        elif loop_mode == "queue":
            self.loop_button.label = "Loop: Queue"
            self.loop_button.emoji = "🔁"
            self.loop_button.style = discord.ButtonStyle.success
        else:
            self.loop_button.label = "Loop: Off"
            self.loop_button.emoji = "🔁"
            self.loop_button.style = discord.ButtonStyle.secondary

        # Shuffle button disabled if not enough upcoming songs
        unplayed_count = len(player.playlist) - (player.index + 1)
        self.shuffle_button.disabled = (unplayed_count <= 1)

    async def _player_ctx(self, interaction):
        """Common guard: playback state must exist and the bot be in voice."""
        player = self.playback.get_player(self.guild_id)
        if player.ctx is None or interaction.guild.voice_client is None:
            await interaction.response.send_message(
                "Nothing is playing — use `!play <song>` first.", ephemeral=True
            )
            return None, None
        return player, player.ctx

    @discord.ui.button(emoji="⏮️", style=discord.ButtonStyle.secondary, custom_id="prev", row=0)
    async def prev_button(self, interaction, button):
        player, ctx = await self._player_ctx(interaction)
        if player is None:
            return
        if player.index > 0:
            await interaction.response.defer()
            await self.playback.play_index(ctx, player.index - 1)
        else:
            await interaction.response.send_message("No previous song in history.", ephemeral=True)

    @discord.ui.button(label="Pause", emoji="⏸️", style=discord.ButtonStyle.secondary, custom_id="pause", row=0)
    async def pause_button(self, interaction, button):
        player, ctx = await self._player_ctx(interaction)
        if player is None:
            return
        await interaction.response.defer()
        voice = ctx.guild.voice_client
        if voice and voice.is_paused():
            await self.playback.resume(ctx)
        elif voice and voice.is_playing():
            await self.playback.pause(ctx)
        else:
            await self.playback.refresh_player(ctx)

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary, custom_id="next", row=0)
    async def next_button(self, interaction, button):
        player, ctx = await self._player_ctx(interaction)
        if player is None:
            return
        if player.index + 1 < len(player.playlist):
            await interaction.response.defer()
            await self.playback.play_index(ctx, player.index + 1)
        elif getattr(player, "loop_mode", "off") == "queue" and len(player.playlist) > 0:
            await interaction.response.defer()
            await self.playback.play_index(ctx, 0)
        else:
            await interaction.response.send_message("No next song in the queue.", ephemeral=True)

    @discord.ui.button(label="Shuffle", emoji="🔀", style=discord.ButtonStyle.secondary, custom_id="shuffle", row=0)
    async def shuffle_button(self, interaction, button):
        player, ctx = await self._player_ctx(interaction)
        if player is None:
            return
        if self.playback.shuffle(self.guild_id):
            await interaction.response.send_message("🔀 Shuffled upcoming songs in the queue!", ephemeral=True)
            await self.playback.refresh_player(ctx)
        else:
            await interaction.response.send_message("Not enough upcoming songs in the queue to shuffle.", ephemeral=True)

    @discord.ui.button(label="Stop", emoji="⏹️", style=discord.ButtonStyle.danger, custom_id="stop", row=0)
    async def stop_button(self, interaction, button):
        player, ctx = await self._player_ctx(interaction)
        if player is None:
            return
        await interaction.response.defer()
        await self.playback.disconnect_and_cleanup(ctx)

    @discord.ui.button(label="1.0x", emoji="⚡", custom_id="speed_1", row=1)
    async def speed1_button(self, interaction, button):
        await self._set_speed(interaction, 1)

    @discord.ui.button(label="2.0x", emoji="⚡", custom_id="speed_2", row=1)
    async def speed2_button(self, interaction, button):
        await self._set_speed(interaction, 2)

    @discord.ui.button(label="3.0x", emoji="⚡", custom_id="speed_3", row=1)
    async def speed3_button(self, interaction, button):
        await self._set_speed(interaction, 3)

    @discord.ui.button(label="Loop: Off", emoji="🔁", custom_id="loop", row=1)
    async def loop_button(self, interaction, button):
        player, ctx = await self._player_ctx(interaction)
        if player is None:
            return
        modes = ["off", "track", "queue"]
        curr = getattr(player, "loop_mode", "off")
        curr_idx = modes.index(curr) if curr in modes else 0
        player.loop_mode = modes[(curr_idx + 1) % len(modes)]
        await interaction.response.defer()
        await self.playback.refresh_player(ctx)

    @discord.ui.button(label="Queue", emoji="📜", style=discord.ButtonStyle.secondary, custom_id="queue", row=1)
    async def queue_button(self, interaction, button):
        player = self.playback.get_player(self.guild_id)
        if not player.playlist:
            await interaction.response.send_message("The queue is currently empty.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"📜 Queue for {interaction.guild.name}",
            color=0x5865F2,
        )
        lines = []
        for i, item in enumerate(player.playlist):
            title = getattr(item, "title", None) or (item[0] if isinstance(item, (tuple, list)) else str(item))
            duration = getattr(item, "duration", None)
            dur_str = f" `[{format_duration(duration)}]`" if duration else ""
            if i == player.index:
                lines.append(f"▶️ **{i + 1}. {title}**{dur_str} *(Now Playing)*")
            elif i < player.index:
                lines.append(f"⏮️ `{i + 1}.` ~~{title}~~{dur_str}")
            else:
                lines.append(f"`{i + 1}.` {title}{dur_str}")

        if len(lines) > 15:
            embed.description = "\n".join(lines[:15]) + f"\n\n*...and {len(lines) - 15} more tracks in queue*"
        else:
            embed.description = "\n".join(lines)

        loop_mode = getattr(player, "loop_mode", "off").capitalize()
        embed.set_footer(text=f"Total: {len(player.playlist)} songs • Loop Mode: {loop_mode}")
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def _set_speed(self, interaction, value):
        player, ctx = await self._player_ctx(interaction)
        if player is None:
            return
        await interaction.response.defer()
        await self.playback.set_speed(ctx, value)
