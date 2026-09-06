---
name: audio-streaming-engine
description: >-
  Use this skill when working on yt-dlp downloading, media ingestion, audio formats,
  FFmpeg filters (speed, pitch, normalization, equalizers), PO token provider integration,
  SoundCloud/YouTube fallback pipelines, or discord.py audio clock synchronization and jitter.
---

# Audio Streaming Engine Skill

This skill guides engineering tasks related to media ingestion, audio extraction, stream filtering, and voice packet synchronization in the Discord Music Bot.

## Core Directives

1. **Offload Blocking Downloads**:
   - `yt-dlp` operations block the Python GIL. Always wrap download and extraction calls with:
     ```python
     await asyncio.to_thread(self.download, search)
     ```
2. **Preserve Fallback Hierarchy**:
   - Direct search queries: Default to SoundCloud search (`scsearch:<query>`) because SoundCloud does not apply datacenter IP blocks.
   - YouTube URLs: First try direct download with the `bgutil-ytdlp-pot-provider` PO token sidecar.
   - If a `DownloadError` is raised, fetch the title from YouTube's unblocked `https://www.youtube.com/oembed` endpoint, clean the title of noisy promotional text (`part.split("|")[:2]`), and retrieve the audio from SoundCloud.
3. **FFmpeg Filtergraph Pacing**:
   - Speed filters use FFmpeg's `atempo`. Since `atempo` only supports ratios between 0.5 and 2.0 per filter stage, chain stages for higher speeds:
     - 1x: `-vn`
     - 2x: `-vn -filter:a atempo=2.0`
     - 3x: `-vn -filter:a atempo=2.0,atempo=1.5`
4. **Audio Clock Synchronization & Jitter Patch**:
   - Refer to [`audio_patch.py`](file:///d:/Discord/bots/discord-music-bot/discord-music-bot/src/discord_music_bot/core/audio_patch.py).
   - If audio bursts (playing at 2x speed after a stall) return, verify that `patch_audio_player()` is invoked before the bot runs.
   - The threshold is `max_lag = 0.2` seconds. If `now - next_time > max_lag`, resynchronize the reference clock `self._start` rather than dumping backlogged packets into Discord's voice socket.

## Adding Audio Effects & Equalizers

When adding volume, bass boost, or nightcore filters:
1. Ensure the `-vn` flag is always present to omit video streams and conserve memory.
2. Construct the audio filter graph cleanly:
   ```python
   # Example: Nightcore (speed up + pitch up)
   "-vn -filter:a asetrate=48000*1.25,aresample=48000,atempo=1.0"
   # Example: Bass boost
   "-vn -filter:a equalizer=f=60:width_type=h:width=50:g=10"
   ```
3. Test audio playback under CPU limits to ensure filter complexity does not induce packet loss.
