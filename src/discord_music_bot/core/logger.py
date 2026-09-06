"""Class-based structured logger for Discord Music Bot, Docker, and Oracle Cloud Logging."""

from __future__ import annotations

import logging
import os
import sys
import time
from typing import Any


class UTCFormatter(logging.Formatter):
    """Custom logging formatter that enforces UTC timestamps for cloud audit consistency."""

    converter = time.gmtime

    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        ct = self.converter(record.created)
        if datefmt:
            s = time.strftime(datefmt, ct)
        else:
            s = time.strftime("%Y-%m-%d %H:%M:%S", ct)
        return f"{s} UTC"


class BotLogger:
    """Class-based logger providing structured, timestamped logs with context support.

    Designed for containerized execution and Oracle Cloud Audit / Logging pipelines.
    """

    _configured = False
    _default_level = logging.INFO

    @classmethod
    def setup(cls, level_name: str | None = None) -> None:
        """Configure root-level bot logging once at startup."""
        if cls._configured:
            return

        level_str = (level_name or os.environ.get("LOG_LEVEL", "INFO")).upper()
        log_level = getattr(logging, level_str, logging.INFO)
        cls._default_level = log_level

        # Configure root handler for the package namespace
        root_logger = logging.getLogger("discord_music_bot")
        root_logger.setLevel(log_level)
        root_logger.handlers.clear()

        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(log_level)

        formatter = UTCFormatter(
            fmt="[%(asctime)s] [%(levelname)-5s] [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)
        root_logger.propagate = False

        cls._configured = True

    def __init__(self, name: str):
        """Initialize a logger instance under the discord_music_bot namespace."""
        if not self._configured:
            self.setup()

        full_name = f"discord_music_bot.{name}" if not name.startswith("discord_music_bot") else name
        self._logger = logging.getLogger(full_name)

    def _format_msg(self, msg: str, guild_id: int | str | None = None) -> str:
        if guild_id is not None:
            return f"[Guild:{guild_id}] {msg}"
        return msg

    def debug(self, msg: str, guild_id: int | str | None = None, *args: Any, **kwargs: Any) -> None:
        """Log a debug message."""
        self._logger.debug(self._format_msg(msg, guild_id), *args, **kwargs)

    def info(self, msg: str, guild_id: int | str | None = None, *args: Any, **kwargs: Any) -> None:
        """Log an informational message."""
        self._logger.info(self._format_msg(msg, guild_id), *args, **kwargs)

    def warning(self, msg: str, guild_id: int | str | None = None, *args: Any, **kwargs: Any) -> None:
        """Log a warning message."""
        self._logger.warning(self._format_msg(msg, guild_id), *args, **kwargs)

    def error(
        self,
        msg: str,
        guild_id: int | str | None = None,
        exc_info: bool = False,
        *args: Any,
        **kwargs: Any,
    ) -> None:
        """Log an error message."""
        self._logger.error(self._format_msg(msg, guild_id), exc_info=exc_info, *args, **kwargs)

    def exception(self, msg: str, guild_id: int | str | None = None, *args: Any, **kwargs: Any) -> None:
        """Log an exception with traceback."""
        self._logger.exception(self._format_msg(msg, guild_id), *args, **kwargs)
