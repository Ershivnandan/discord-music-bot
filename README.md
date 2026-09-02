# Discord Music Bot

A simple Discord music bot using discord.py + yt-dlp. Plays audio from YouTube by URL or song name.

## Commands

| Command | Description |
| --- | --- |
| `!join` | Join your voice channel |
| `!play <song or URL>` | Play / queue a song |
| `!skip` | Skip the current song |
| `!pause` | Pause playback |
| `!resume` | Resume playback |
| `!leave` | Clear queue and disconnect |

## Local setup

Requires Python 3.13+, [uv](https://docs.astral.sh/uv/), and FFmpeg installed on your system.

```sh
cp .env.example .env   # then put your real bot token in .env
uv sync
uv run discord-music-bot
```

## Deploy to Render

1. Push this repo to GitHub.
2. On [Render](https://render.com), click **New → Blueprint** and select the repo — it picks up `render.yaml` automatically. (Or create a **Web Service** manually with runtime **Docker**.)
3. In the service's **Environment** settings, add `DISCORD_TOKEN` with your bot token.
4. Deploy. The Dockerfile installs FFmpeg and runs the bot; a small HTTP health server binds to `PORT` so Render's free web service stays happy.

> **Keep-alive:** Render's free tier spins the service down after ~15 minutes without inbound traffic. The bot handles this itself: it pings its own public URL (from Render's `RENDER_EXTERNAL_URL` env var) every 10 minutes, so no external pinger is needed. As a backup you can still point UptimeRobot / cron-job.org at the service URL, or set `KEEP_ALIVE_URL` to override the ping target.

## YouTube blocking ("Sign in to confirm you're not a bot")

YouTube challenges datacenter IPs like Render's. Two layers handle this:

1. **PO tokens (automatic):** the Docker image runs the [bgutil PO-token provider](https://github.com/Brainicism/bgutil-ytdlp-pot-provider) alongside the bot; yt-dlp's plugin picks it up at `127.0.0.1:4416` with zero config. This is usually enough — try without cookies first. When updating, keep the pip plugin version (pyproject) and the server version (Dockerfile `--branch` tag) identical.
2. **Cookies (fallback, optional):** if YouTube still blocks, upload a `cookies.txt` as a Render Secret File. **Export them the right way or they die after a few requests:**
   - Open a **private/incognito window**, log in to YouTube (a throwaway account is safer)
   - Visit `https://www.youtube.com/robots.txt` in that same tab
   - Export cookies with a browser extension (e.g. "Get cookies.txt LOCALLY")
   - **Close the incognito window immediately** and never log into that account in a normal browser tab — otherwise YouTube rotates the cookies and the exported file stops working

## Security

Never commit your bot token. It's read from the `DISCORD_TOKEN` environment variable (locally via `.env`, which is gitignored). If a token ever leaks, reset it immediately in the [Discord Developer Portal](https://discord.com/developers/applications).
