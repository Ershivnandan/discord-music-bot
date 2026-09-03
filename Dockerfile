FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

# Show print() output in docker logs immediately instead of buffering it
ENV PYTHONUNBUFFERED=1

# FFmpeg is required for voice playback
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

# Deno: yt-dlp needs a JS runtime to decipher YouTube's player signatures
COPY --from=denoland/deno:bin /deno /usr/local/bin/deno

WORKDIR /app

# Install dependencies first for better layer caching
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY . .
RUN uv sync --frozen --no-dev

CMD ["uv", "run", "discord-music-bot"]
