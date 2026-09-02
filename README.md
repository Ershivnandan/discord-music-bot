# Discord Music Bot

A simple, lightweight Discord music bot using discord.py + yt-dlp. Plays audio from SoundCloud by song name (or any direct/supported URL).

## Commands

| Command | Description |
| --- | --- |
| `!join` | Join your voice channel |
| `!play <song or URL>` | Play / queue a song (searches SoundCloud) |
| `!next` / `!skip` | Next song |
| `!prev` | Previous song |
| `!speed 1\|2\|3` | Playback speed (1x / 2x / 3x); applies immediately |
| `!pause` | Pause playback |
| `!resume` | Resume playback |
| `!leave` | Clear queue and disconnect |

## Why SoundCloud and not YouTube?

YouTube aggressively blocks datacenter IPs (like Render's) with "sign in to confirm you're not a bot" checks; working around it needs PO-token servers and browser cookies that expire. SoundCloud doesn't block server IPs, so the bot stays small and reliable.

## Local setup

Requires Python 3.13+, [uv](https://docs.astral.sh/uv/), and FFmpeg installed on your system.

```sh
cp .env.example .env   # then put your real bot token in .env
uv sync
uv run discord-music-bot
```

## Deploy to Render

1. Push this repo to GitHub.
2. On [Render](https://render.com), click **New → Blueprint** and select the repo — it picks up `render.yaml` automatically.
3. In the service's **Environment** settings, add `DISCORD_TOKEN` with your bot token.
4. Deploy. The Dockerfile installs FFmpeg and runs the bot; a small HTTP health server binds to `PORT` so Render's free web service stays happy.

> **Keep-alive:** Render's free tier spins the service down after ~15 minutes without inbound traffic. The bot handles this itself: it pings its own public URL (from Render's `RENDER_EXTERNAL_URL` env var) every few minutes, so no external pinger is needed. Set `KEEP_ALIVE_URL` to override the ping target.

> **Audio quality note:** Render's free instances get ~0.1 CPU. The bot minimizes CPU use (Opus encoding happens inside FFmpeg, progressive streams instead of HLS), but if playback still stutters under load, a paid instance is the fix.

## Security

Never commit your bot token. It's read from the `DISCORD_TOKEN` environment variable (locally via `.env`, which is gitignored). If a token ever leaks, reset it immediately in the [Discord Developer Portal](https://discord.com/developers/applications).
