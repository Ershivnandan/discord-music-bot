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

## How YouTube playback works on a server

YouTube blocks datacenter IPs with "sign in to confirm you're not a bot" checks. The bot handles this in three layers:

1. **PO tokens** — the `pot-provider` sidecar container (see `docker-compose.yml`) generates the tokens YouTube wants, so direct YouTube links work from server IPs without an account.
2. **Cookies (optional)** — set `YTDLP_COOKIES_FILE` to a Netscape-format `cookies.txt` for logged-in access if PO tokens ever stop being enough.
3. **SoundCloud fallback** — if a YouTube download still fails, the bot looks up the video title via YouTube's oEmbed API (which isn't IP-blocked) and plays the closest SoundCloud match.

Plain-text searches (`!play <song name>`) go straight to SoundCloud, which doesn't block server IPs.

## Local setup

Requires Python 3.13+, [uv](https://docs.astral.sh/uv/), and FFmpeg installed on your system.

```sh
cp .env.example .env   # then put your real bot token in .env
uv sync
uv run discord-music-bot
```

## Deployment (Oracle Cloud VM + GitHub Actions)

The bot runs in Docker (via `docker compose`, together with the PO-token
sidecar) on an Oracle Cloud Always Free ARM VM. Every push to `master`
triggers `.github/workflows/deploy.yml`, which SSHes into the VM, pulls,
rebuilds and restarts the containers.

### One-time VM setup (Oracle Linux 9, user `opc`)

```sh
ssh opc@<VM_PUBLIC_IP>
sudo dnf install -y dnf-utils git
sudo dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker opc
exit  # log back in so the docker group applies

ssh opc@<VM_PUBLIC_IP>
git clone https://github.com/Ershivnandan/discord-music-bot.git ~/bot
echo 'DISCORD_TOKEN=<your-bot-token>' > ~/bot.env
ln -sf ~/bot.env ~/bot/.env
cd ~/bot && docker compose up -d --build
```

### One-time GitHub setup

In the repo: **Settings → Secrets and variables → Actions → New repository secret**

| Secret | Value |
| --- | --- |
| `ORACLE_HOST` | The VM's public IP |
| `ORACLE_SSH_KEY` | The **private** SSH key for the VM (the whole file, including BEGIN/END lines) |

After that, `git push` = auto deploy. Check progress in the repo's **Actions** tab; logs on the VM with `docker compose logs -f` (run from `~/bot`).

## Security

Never commit your bot token. It's read from the `DISCORD_TOKEN` environment variable (locally via `.env`, which is gitignored). If a token ever leaks, reset it immediately in the [Discord Developer Portal](https://discord.com/developers/applications).
