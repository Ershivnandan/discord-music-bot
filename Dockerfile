# Build the bgutil PO-token provider server. Its version MUST match the
# bgutil-ytdlp-pot-provider pip plugin version pinned in pyproject.toml.
FROM node:20-bookworm-slim AS bgutil
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
RUN git clone --depth 1 --branch 1.3.2 https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git /bgutil
WORKDIR /bgutil/server
RUN npm ci && npx tsc

FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

# FFmpeg for voice playback; libatomic1/libstdc++6 for the node binary below
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg libatomic1 libstdc++6 \
    && rm -rf /var/lib/apt/lists/*

# Deno is the JS runtime yt-dlp uses to solve YouTube's JS challenges
COPY --from=denoland/deno:bin /deno /usr/local/bin/deno

# Node runtime + built bgutil server, which mints YouTube PO tokens
# (required on datacenter IPs to avoid "confirm you're not a bot" blocks)
COPY --from=bgutil /usr/local/bin/node /usr/local/bin/node
COPY --from=bgutil /bgutil/server /bgutil/server

WORKDIR /app

# Install dependencies first for better layer caching
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project --no-dev

COPY . .
RUN uv sync --frozen --no-dev

CMD ["sh", "/app/start.sh"]
