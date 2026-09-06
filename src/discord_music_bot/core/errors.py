"""Centralized, class-based exception hierarchy for Discord Music Bot."""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from .logger import BotLogger


class MusicBotError(Exception):
    """Base exception for all domain-specific errors in the bot."""

    default_code = "ERR_INTERNAL"
    default_message = "An unexpected error occurred."

    def __init__(
        self,
        message: str | None = None,
        detail: str | None = None,
        code: str | None = None,
        guild_id: int | str | None = None,
        recoverable: bool = True,
    ) -> None:
        self.message = message or self.default_message
        super().__init__(self.message)
        self.detail = detail
        self.code = code or self.default_code
        self.guild_id = guild_id
        self.recoverable = recoverable

    def to_embed(self) -> discord.Embed:
        """Render a clean, user-friendly Discord error embed."""
        embed = discord.Embed(
            title=f"⚠️ {self.code}",
            description=self.message,
            color=0xED4245,  # Discord Red
        )
        if self.detail:
            cleaned_detail = str(self.detail).strip()
            if len(cleaned_detail) > 250:
                cleaned_detail = cleaned_detail[:247] + "..."
            embed.add_field(name="Details", value=f"`{cleaned_detail}`", inline=False)
        return embed

    def log_with(self, logger: BotLogger) -> None:
        """Emit a formatted log message with technical details to BotLogger."""
        extra = f" | Details: {self.detail}" if self.detail else ""
        log_fn = logger.warning if self.recoverable else logger.error
        log_fn(f"[{self.code}] {self.message}{extra}", guild_id=self.guild_id)


class DownloadError(MusicBotError):
    """Raised when a song download or metadata extraction fails."""

    default_code = "ERR_DOWNLOAD_FAILED"
    default_message = "Failed to download or extract the requested song."


class YouTubeBlockedError(DownloadError):
    """Raised when YouTube challenges or blocks datacenter IP download requests."""

    default_code = "ERR_YOUTUBE_BLOCKED"
    default_message = "YouTube blocked direct download from the server IP."


class VoiceChannelError(MusicBotError):
    """Raised when voice channel state or connection requirements are unmet."""

    default_code = "ERR_VOICE_REQUIRED"
    default_message = "You must be connected to a voice channel first."


class PlaybackError(MusicBotError):
    """Raised when FFmpeg or discord.py fails during playback."""

    default_code = "ERR_PLAYBACK_FAILED"
    default_message = "An error occurred during audio stream playback."


class QueueError(MusicBotError):
    """Raised when invalid queue operations or out-of-bounds requests occur."""

    default_code = "ERR_QUEUE_EMPTY"
    default_message = "No song available in the queue."
