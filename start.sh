#!/bin/sh
# Start the bgutil PO-token provider server (yt-dlp's plugin finds it
# automatically at 127.0.0.1:4416), then the bot itself.
echo "Starting bgutil PO-token provider server..."
node /bgutil/server/build/main.js &
exec uv run discord-music-bot
