---
name: devops-cloud-resilience
description: >-
  Use this skill when modifying Dockerfile, docker-compose.yml, GitHub Actions deployment
  workflows, Oracle Cloud VM configuration, Render web service setup, Deno JS runtime bundling,
  or HTTP health-check keep-alive loops.
---

# DevOps & Cloud Resilience Skill

This skill guides containerization, cloud resource optimization, and deployment automation for the Discord Music Bot.

## Docker Architecture

The containerized deployment consists of two services in [`docker-compose.yml`](file:///d:/Discord/bots/discord-music-bot/discord-music-bot/docker-compose.yml):

1. **`bot` Container**:
   - Base image: `ghcr.io/astral-sh/uv:python3.13-bookworm-slim`.
   - Injects `deno` binary directly from `denoland/deno:bin` to provide a headless JS engine for `yt-dlp` cipher decoding.
   - Installs system `ffmpeg`.
   - Uses layer caching with `uv sync --frozen --no-install-project --no-dev`.
   - Exposes port `8080` for health check pings.
2. **`pot-provider` Sidecar**:
   - Image: `brainicism/bgutil-ytdlp-pot-provider`.
   - Listens on `http://pot-provider:4416` on the internal Docker network.
   - Generates YouTube PO tokens so server IPs are not blocked by Google datacenter bot checks.

## Oracle Cloud Always Free ARM Deployment

Deployment is triggered on pushes to `master` via [`.github/workflows/deploy.yml`](file:///d:/Discord/bots/discord-music-bot/discord-music-bot/.github/workflows/deploy.yml) using `appleboy/ssh-action@v1`.

### Host Environment Setup (Oracle Linux 9)
```sh
# Required packages
sudo dnf install -y dnf-utils git docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker opc

# Bot directory & environment
git clone https://github.com/Ershivnandan/discord-music-bot.git ~/bot
echo 'DISCORD_TOKEN=<your-token>' > ~/bot.env
ln -sf ~/bot.env ~/bot/.env
cd ~/bot && docker compose up -d --build
```

### GitHub Secrets Configuration
- `ORACLE_HOST`: Public IPv4 address of the Oracle Cloud instance.
- `ORACLE_SSH_KEY`: Full private SSH key (including `-----BEGIN OPENSSH PRIVATE KEY-----` and trailing end tag).

## Keep-Alive & Health Monitoring

Render and other free hosts sleep inactive containers after 15 minutes of zero HTTP traffic:
1. `HealthServer` starts a minimal daemon thread on `0.0.0.0:8080`.
2. Responds `200 OK` ("Bot is running") to GET requests.
3. If `KEEP_ALIVE_URL` is set, `MusicBot` pings its own external URL every 5 minutes via an `@tasks.loop(minutes=5)` background task.
