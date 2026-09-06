# Discord Music Bot — Agent Rules & Engineering Guidelines

This document provides system-level rules, architectural guidelines, and role-based domain routing for AI agents operating on this repository.

---

## 1. Core Architectural Constraints

Every agent modifying or adding code to this project **must** adhere to the following non-negotiable principles:

1. **Strict Low-Resource Budgeting**:
   - The bot is designed to run on constrained environments (such as Render 0.1-CPU instances or Oracle Cloud Always Free ARM VMs).
   - **Never stream raw high-bitrate video or uncompressed audio over the wire**: always download/cache songs locally or use progressive audio streams (`bestaudio[protocol!*=m3u8]/bestaudio/best`).
   - Rate limit downloads (`ratelimit` in `YDL_OPTIONS`) to avoid starving the CPU and stalling real-time Discord audio threads.
   - Clean up temporary audio files from `DOWNLOAD_DIR` immediately upon track removal, playlist clear, or bot disconnect.

2. **Non-Blocking Async Event Loop**:
   - The Discord gateway operates on an `asyncio` event loop.
   - **Never run blocking operations synchronously** (e.g., `yt_dlp.YoutubeDL.extract_info`, file operations, heavy regex parsing). Always offload blocking work using `await asyncio.to_thread(...)`.

3. **Concurrency & Race Condition Prevention**:
   - Track transitions trigger the FFmpeg callback `after_playing(error)`.
   - Always maintain and increment the `GuildPlayer.generation` counter when manually skipping, switching speed, or stopping. The `after_playing` callback must verify `generation == player.generation` before advancing to avoid double-play bugs.

4. **YouTube Datacenter IP Bypass Resilience**:
   - YouTube blocks requests from datacenter IPs. The three-layer mitigation must remain intact:
     1. Proof-of-Origin (PO) token sidecar (`POT_PROVIDER_URL`).
     2. Optional Netscape cookie file (`YTDLP_COOKIES_FILE`).
     3. YouTube oEmbed fallback (`youtube.com/oembed`) + SoundCloud search (`scsearch`).
   - Plain text queries (`!play <song name>`) should default directly to SoundCloud (`scsearch`) to avoid bot checks.

5. **Discord Audio Clock Resync**:
   - Preserve `core/audio_patch.py`. It monkey-patches `discord.player.AudioPlayer._do_run` to resync audio clock packets if system latency exceeds 200ms, preventing jarring 2x speed burst catches after CPU stalls.

---

## 2. Specialized Agent Domain Routing

When working on tasks in this repository, activate the appropriate specialized skill or assume the corresponding domain persona:

| Domain / Task | Specialized Skill | Target Directory Scope |
| :--- | :--- | :--- |
| **Audio Ingestion & Media Filters** | `audio-streaming-engine` | `src/discord_music_bot/core/downloader.py`, `core/audio_patch.py`, `config.py` |
| **Discord UI, Views & Commands** | `discord-ui-architect` | `src/discord_music_bot/ui/`, `src/discord_music_bot/cogs/` |
| **Queue, Playlists & Concurrency** | `queue-state-manager` | `src/discord_music_bot/core/playback.py` |
| **Docker, Cloud Hosting & CI/CD** | `devops-cloud-resilience` | `Dockerfile`, `docker-compose.yml`, `.github/`, `web/health.py` |
| **Automated Testing & Edge-Case QA**| `music-bot-qa-testing` | `tests/`, test fixtures, mock harnesses |

---

## 3. Technology Stack & Tools

- **Language**: Python 3.13+
- **Package & Environment Manager**: [uv](https://docs.astral.sh/uv/) (`uv sync`, `uv run ...`)
- **Discord Framework**: `discord.py[voice] >= 2.7.1`
- **Audio Decoding**: `yt-dlp >= 2026.8.19`, FFmpeg with `atempo` filters
- **JS Runtime**: Deno (for YouTube player signature deciphering in Docker)
- **Sidecar**: `bgutil-ytdlp-pot-provider`
- **Deployment**: Docker Compose on Oracle Linux ARM VM via GitHub Actions SSH deployment
