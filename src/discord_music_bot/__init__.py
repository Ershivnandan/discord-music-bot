import asyncio
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import aiohttp
import discord
import yt_dlp
from discord.ext import commands, tasks
from dotenv import load_dotenv

load_dotenv()

intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

YDL_OPTIONS = {
    # Prefer progressive (non-HLS) streams: they buffer better and support
    # ffmpeg's reconnect flags, which HLS doesn't
    "format": "bestaudio[protocol!*=m3u8]/bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    # SoundCloud search: unlike YouTube, it doesn't block server IPs
    "default_search": "scsearch",
}

FFMPEG_OPTIONS = {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn",
}

queues = {}  # guild_id -> list of (title, url)


def get_queue(guild_id):
    return queues.setdefault(guild_id, [])


# Render sets RENDER_EXTERNAL_URL automatically; pinging our own public URL
# counts as inbound traffic, so the free instance never spins down.
KEEP_ALIVE_URL = os.environ.get("KEEP_ALIVE_URL") or os.environ.get("RENDER_EXTERNAL_URL")


@tasks.loop(minutes=5)
async def keep_alive():
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(KEEP_ALIVE_URL, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                print(f"Keep-alive ping: {resp.status}")
    except Exception as e:
        print(f"Keep-alive ping failed: {e}")


@bot.event
async def on_ready():
    print(f"Logged in as {bot.user}")
    if KEEP_ALIVE_URL and not keep_alive.is_running():
        keep_alive.start()
        print(f"Keep-alive pings started for {KEEP_ALIVE_URL}")


@bot.command(name="join")
async def join(ctx):
    if ctx.author.voice is None:
        await ctx.send("You need to be in a voice channel first.")
        return
    channel = ctx.author.voice.channel
    if ctx.voice_client is None:
        await channel.connect()
    else:
        await ctx.voice_client.move_to(channel)


def extract_info(search: str):
    with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
        info = ydl.extract_info(search, download=False)
        if "entries" in info:  # came from a search
            info = info["entries"][0]
        return info.get("title", "Unknown title"), info["url"]


@bot.command(name="play")
async def play(ctx, *, search: str):
    if ctx.voice_client is None:
        if ctx.author.voice is None:
            await ctx.send("Join a voice channel first.")
            return
        await ctx.author.voice.channel.connect()

    async with ctx.typing():
        try:
            # yt-dlp is blocking; run it off the event loop
            title, url = await asyncio.to_thread(extract_info, search)
        except yt_dlp.utils.DownloadError as e:
            await ctx.send(f"Couldn't fetch that song: {str(e)[:200]}")
            return

    queue = get_queue(ctx.guild.id)
    queue.append((title, url))
    await ctx.send(f"Queued: **{title}**")

    if not ctx.voice_client.is_playing():
        await play_next(ctx)


async def play_next(ctx):
    queue = get_queue(ctx.guild.id)
    if not queue:
        return

    title, url = queue.pop(0)
    # FFmpegOpusAudio encodes opus inside ffmpeg (C), so Python doesn't
    # re-encode PCM — much lighter on Render's 0.1-CPU free instance
    source = await discord.FFmpegOpusAudio.from_probe(url, **FFMPEG_OPTIONS)

    def after_playing(error):
        if error:
            print(f"Playback error: {error}")
        coro = play_next(ctx)
        fut = asyncio.run_coroutine_threadsafe(coro, bot.loop)
        try:
            fut.result()
        except Exception as e:
            print(e)

    ctx.voice_client.play(source, after=after_playing)
    await ctx.send(f"Now playing: **{title}**")


@bot.command(name="skip")
async def skip(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.stop()  # triggers after_playing -> play_next
        await ctx.send("Skipped.")


@bot.command(name="pause")
async def pause(ctx):
    if ctx.voice_client and ctx.voice_client.is_playing():
        ctx.voice_client.pause()


@bot.command(name="resume")
async def resume(ctx):
    if ctx.voice_client and ctx.voice_client.is_paused():
        ctx.voice_client.resume()


@bot.command(name="leave")
async def leave(ctx):
    if ctx.voice_client:
        queues[ctx.guild.id] = []
        await ctx.voice_client.disconnect()


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is running")

    def log_message(self, format, *args):
        pass  # keep logs clean


def start_health_server():
    # Render free web services require a bound port; this also serves
    # as the health-check endpoint to keep the service alive.
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    print(f"Health server listening on port {port}")


def main() -> None:
    token = os.environ.get("DISCORD_TOKEN")
    if not token:
        raise SystemExit("DISCORD_TOKEN environment variable is not set.")
    start_health_server()
    bot.run(token)
