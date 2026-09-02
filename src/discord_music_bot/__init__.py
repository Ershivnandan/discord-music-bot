import asyncio
import os
import tempfile
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

# Songs are fully downloaded before playing: streaming over the network on
# Render's tiny free instance causes crackling/lag whenever the connection
# jitters, while playing a local file is rock solid.
DOWNLOAD_DIR = os.path.join(tempfile.gettempdir(), "discord-music")
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

YDL_OPTIONS = {
    # Prefer progressive (non-HLS) streams: single small file, fast download
    "format": "bestaudio[protocol!*=m3u8]/bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    # SoundCloud search: unlike YouTube, it doesn't block server IPs
    "default_search": "scsearch",
    "outtmpl": os.path.join(DOWNLOAD_DIR, "%(id)s.%(ext)s"),
}

# ffmpeg's atempo filter caps at 2.0 per stage, so 3x chains two stages
SPEED_FILTERS = {
    1: "-vn",
    2: "-vn -filter:a atempo=2.0",
    3: "-vn -filter:a atempo=2.0,atempo=1.5",
}


class GuildPlayer:
    """Per-guild playback state: full session playlist + current position."""

    def __init__(self):
        self.playlist = []  # list of (title, file path); kept for !prev
        self.index = -1  # position of the currently playing song
        self.speed = 1
        # Bumped on every (re)start; stale after-callbacks see a mismatch
        # and skip auto-advancing, so manual next/prev/speed don't double-play
        self.generation = 0


players = {}  # guild_id -> GuildPlayer


def get_player(guild_id) -> GuildPlayer:
    return players.setdefault(guild_id, GuildPlayer())


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


COMMANDS_MESSAGE = (
    "🎵 **I'm here! Commands:**\n"
    "`!play <song or URL>` — play a song, or queue it if one is playing\n"
    "`!next` (or `!skip`) — next song\n"
    "`!prev` — previous song\n"
    "`!speed 1|2|3` — playback speed (1x / 2x / 3x)\n"
    "`!pause` / `!resume` — pause / resume playback\n"
    "`!leave` — clear the queue and disconnect\n"
    "`!join` — pull me into your voice channel"
)


@bot.command(name="join")
async def join(ctx):
    if ctx.author.voice is None:
        await ctx.send("You need to be in a voice channel first.")
        return
    channel = ctx.author.voice.channel
    if ctx.voice_client is None:
        await channel.connect()
        await ctx.send(COMMANDS_MESSAGE)
    else:
        await ctx.voice_client.move_to(channel)


def download_song(search: str):
    with yt_dlp.YoutubeDL(YDL_OPTIONS) as ydl:
        info = ydl.extract_info(search, download=True)
        if "entries" in info:  # came from a search
            info = info["entries"][0]
        return info.get("title", "Unknown title"), ydl.prepare_filename(info)


async def play_index(ctx, index: int):
    """Start playing playlist[index], stopping whatever is on now."""
    player = get_player(ctx.guild.id)
    if not 0 <= index < len(player.playlist):
        return
    player.index = index
    player.generation += 1
    generation = player.generation

    voice = ctx.voice_client
    if voice.is_playing() or voice.is_paused():
        voice.stop()

    title, path = player.playlist[index]
    source = discord.FFmpegOpusAudio(path, options=SPEED_FILTERS[player.speed])

    def after_playing(error):
        if error:
            print(f"Playback error: {error}")
        if generation != player.generation:
            return  # superseded by a manual next/prev/speed restart
        fut = asyncio.run_coroutine_threadsafe(advance(ctx), bot.loop)
        try:
            fut.result()
        except Exception as e:
            print(e)

    voice.play(source, after=after_playing)
    speed_note = f" ({player.speed}x)" if player.speed != 1 else ""
    await ctx.send(f"Now playing: **{title}**{speed_note}")


async def advance(ctx):
    player = get_player(ctx.guild.id)
    if player.index + 1 < len(player.playlist):
        await play_index(ctx, player.index + 1)


@bot.command(name="play")
async def play(ctx, *, search: str):
    if ctx.voice_client is None:
        if ctx.author.voice is None:
            await ctx.send("Join a voice channel first.")
            return
        await ctx.author.voice.channel.connect()
        await ctx.send(COMMANDS_MESSAGE)

    async with ctx.typing():
        try:
            # yt-dlp is blocking; run it off the event loop
            title, path = await asyncio.to_thread(download_song, search)
        except yt_dlp.utils.DownloadError as e:
            await ctx.send(f"Couldn't fetch that song: {str(e)[:200]}")
            return

    player = get_player(ctx.guild.id)
    player.playlist.append((title, path))

    if ctx.voice_client.is_playing() or ctx.voice_client.is_paused():
        await ctx.send(f"Queued: **{title}**")
    else:
        await play_index(ctx, len(player.playlist) - 1)


@bot.command(name="next", aliases=["skip"])
async def next_song(ctx):
    if ctx.voice_client is None:
        return
    player = get_player(ctx.guild.id)
    if player.index + 1 < len(player.playlist):
        await play_index(ctx, player.index + 1)
    else:
        await ctx.send("No next song in the queue.")


@bot.command(name="prev")
async def prev_song(ctx):
    if ctx.voice_client is None:
        return
    player = get_player(ctx.guild.id)
    if player.index > 0:
        await play_index(ctx, player.index - 1)
    else:
        await ctx.send("No previous song.")


@bot.command(name="speed")
async def speed(ctx, value: int):
    if value not in SPEED_FILTERS:
        await ctx.send("Speed can be 1, 2 or 3 (e.g. `!speed 2`).")
        return
    player = get_player(ctx.guild.id)
    if player.speed == value:
        await ctx.send(f"Already at {value}x.")
        return
    player.speed = value
    await ctx.send(f"Speed set to **{value}x**.")
    # Apply immediately by restarting the current song at the new speed
    if ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
        await play_index(ctx, player.index)


@speed.error
async def speed_error(ctx, error):
    if isinstance(error, (commands.BadArgument, commands.MissingRequiredArgument)):
        await ctx.send("Usage: `!speed 1`, `!speed 2` or `!speed 3`.")
    else:
        raise error


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
        player = players.pop(ctx.guild.id, None)
        if player:
            player.generation += 1  # cancel any pending auto-advance
            for _, path in player.playlist:
                try:
                    os.remove(path)
                except OSError:
                    pass
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
