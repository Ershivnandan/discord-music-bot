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

## Deployment (Oracle Cloud VM + GitHub Actions)

The bot runs in Docker on an Oracle Cloud Always Free ARM VM. Every push to
`master` triggers `.github/workflows/deploy.yml`, which SSHes into the VM,
pulls, rebuilds and restarts the container.

### One-time VM setup

```sh
ssh ubuntu@<VM_PUBLIC_IP>
sudo apt update && sudo apt install -y docker.io git
sudo usermod -aG docker ubuntu
exit  # log back in so the docker group applies

ssh ubuntu@<VM_PUBLIC_IP>
git clone https://github.com/Ershivnandan/discord-music-bot.git ~/bot
echo 'DISCORD_TOKEN=<your-bot-token>' > ~/bot.env
cd ~/bot && docker build -t music-bot . && \
  docker run -d --name music-bot --restart unless-stopped --env-file ~/bot.env music-bot
```

### One-time GitHub setup

In the repo: **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Value |
| --- | --- |
| `ORACLE_HOST` | The VM's public IP |
| `ORACLE_SSH_KEY` | The **private** SSH key for the VM (the whole file, including BEGIN/END lines) |

After that, `git push` = auto deploy. Check progress in the repo's **Actions** tab; logs on the VM with `docker logs -f music-bot`.

## Security

Never commit your bot token. It's read from the `DISCORD_TOKEN` environment variable (locally via `.env`, which is gitignored). If a token ever leaks, reset it immediately in the [Discord Developer Portal](https://discord.com/developers/applications).
