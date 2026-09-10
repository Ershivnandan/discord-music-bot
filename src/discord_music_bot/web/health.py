"""HTTP server: serves Render keep-alive health checks, JSON playback API,
and a responsive, animated Web Player Dashboard."""

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Optional

from ..core.logger import BotLogger

PLAYER_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Discord Music Player — Live Dashboard</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=Outfit:wght@500;600;700;800&display=swap" rel="stylesheet">
  <style>
    :root {
      --bg-dark: #090c10;
      --card-bg: rgba(22, 27, 34, 0.75);
      --card-border: rgba(255, 255, 255, 0.1);
      --accent-primary: #8a2be2;
      --accent-secondary: #00f2fe;
      --accent-emerald: #2ecc71;
      --accent-amber: #fee75c;
      --text-main: #f0f6fc;
      --text-muted: #8b949e;
    }

    * {
      box-sizing: border-box;
      margin: 0;
      padding: 0;
    }

    body {
      font-family: 'Inter', sans-serif;
      background-color: var(--bg-dark);
      background-image: 
        radial-gradient(circle at 15% 15%, rgba(138, 43, 226, 0.18), transparent 45%),
        radial-gradient(circle at 85% 85%, rgba(0, 242, 254, 0.15), transparent 45%),
        radial-gradient(circle at 50% 50%, rgba(46, 204, 113, 0.08), transparent 60%);
      background-attachment: fixed;
      color: var(--text-main);
      min-height: 100vh;
      display: flex;
      flex-direction: column;
      align-items: center;
      justify-content: center;
      padding: 24px;
    }

    .dashboard-container {
      width: 100%;
      max-width: 440px;
      perspective: 1000px;
    }

    .player-card {
      background: var(--card-bg);
      backdrop-filter: blur(24px);
      -webkit-backdrop-filter: blur(24px);
      border: 1px solid var(--card-border);
      border-radius: 28px;
      padding: 32px 28px;
      box-shadow: 
        0 25px 60px rgba(0, 0, 0, 0.6),
        0 0 40px rgba(138, 43, 226, 0.12);
      text-align: center;
      transition: transform 0.4s cubic-bezier(0.16, 1, 0.3, 1), box-shadow 0.4s ease;
      animation: floatIn 0.8s cubic-bezier(0.16, 1, 0.3, 1);
    }

    .player-card:hover {
      transform: translateY(-4px);
      box-shadow: 
        0 30px 70px rgba(0, 0, 0, 0.7),
        0 0 50px rgba(0, 242, 254, 0.18);
    }

    @keyframes floatIn {
      from { opacity: 0; transform: translateY(30px) scale(0.96); }
      to { opacity: 1; transform: translateY(0) scale(1); }
    }

    .top-bar {
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 24px;
    }

    .brand-tag {
      font-family: 'Outfit', sans-serif;
      font-weight: 700;
      font-size: 13px;
      letter-spacing: 1px;
      text-transform: uppercase;
      background: linear-gradient(90deg, #a78bfa, #38bdf8);
      -webkit-background-clip: text;
      -webkit-text-fill-color: transparent;
    }

    .status-pill {
      display: inline-flex;
      align-items: center;
      gap: 6px;
      padding: 5px 12px;
      border-radius: 20px;
      font-size: 11px;
      font-weight: 600;
      letter-spacing: 0.5px;
      text-transform: uppercase;
    }

    .status-pill.playing {
      background: rgba(46, 204, 113, 0.15);
      color: var(--accent-emerald);
      border: 1px solid rgba(46, 204, 113, 0.3);
    }

    .status-pill.paused {
      background: rgba(254, 231, 92, 0.15);
      color: var(--accent-amber);
      border: 1px solid rgba(254, 231, 92, 0.3);
    }

    .status-pill.idle {
      background: rgba(139, 148, 158, 0.15);
      color: var(--text-muted);
      border: 1px solid rgba(139, 148, 158, 0.3);
    }

    .status-dot {
      width: 7px;
      height: 7px;
      border-radius: 50%;
      background-color: currentColor;
    }

    .playing .status-dot {
      animation: pulseDot 1.5s infinite;
    }

    @keyframes pulseDot {
      0% { transform: scale(0.9); opacity: 0.7; }
      50% { transform: scale(1.3); opacity: 1; }
      100% { transform: scale(0.9); opacity: 0.7; }
    }

    .artwork-container {
      position: relative;
      width: 220px;
      height: 220px;
      margin: 0 auto 24px;
    }

    .artwork-glow {
      position: absolute;
      inset: -10px;
      border-radius: 26px;
      background: linear-gradient(45deg, var(--accent-primary), var(--accent-secondary));
      opacity: 0.35;
      filter: blur(20px);
      z-index: 0;
      transition: opacity 0.5s ease;
    }

    .album-art {
      position: relative;
      width: 100%;
      height: 100%;
      border-radius: 20px;
      object-fit: cover;
      z-index: 1;
      border: 1px solid rgba(255, 255, 255, 0.15);
      box-shadow: 0 12px 28px rgba(0, 0, 0, 0.5);
      background-color: #161b22;
    }

    .equalizer-wave {
      display: flex;
      align-items: flex-end;
      justify-content: center;
      gap: 4px;
      height: 24px;
      margin-bottom: 18px;
    }

    .eq-bar {
      width: 3.5px;
      border-radius: 3px;
      background: linear-gradient(180deg, var(--accent-secondary), var(--accent-primary));
      height: 4px;
      transition: height 0.2s ease;
    }

    .playing .eq-bar:nth-child(1) { animation: bounce 1.1s infinite alternate ease-in-out; }
    .playing .eq-bar:nth-child(2) { animation: bounce 0.9s infinite alternate ease-in-out 0.15s; }
    .playing .eq-bar:nth-child(3) { animation: bounce 1.3s infinite alternate ease-in-out 0.3s; }
    .playing .eq-bar:nth-child(4) { animation: bounce 0.8s infinite alternate ease-in-out 0.1s; }
    .playing .eq-bar:nth-child(5) { animation: bounce 1.2s infinite alternate ease-in-out 0.25s; }
    .playing .eq-bar:nth-child(6) { animation: bounce 1.0s infinite alternate ease-in-out 0.4s; }

    @keyframes bounce {
      0% { height: 4px; }
      100% { height: 24px; }
    }

    .track-title {
      font-family: 'Outfit', sans-serif;
      font-size: 20px;
      font-weight: 700;
      color: #fff;
      margin-bottom: 6px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
      text-decoration: none;
      display: block;
    }

    .track-title:hover {
      color: var(--accent-secondary);
    }

    .track-artist {
      font-size: 14px;
      color: var(--text-muted);
      margin-bottom: 18px;
      white-space: nowrap;
      overflow: hidden;
      text-overflow: ellipsis;
    }

    .meta-badges {
      display: flex;
      gap: 8px;
      justify-content: center;
      flex-wrap: wrap;
      margin-bottom: 22px;
    }

    .badge {
      font-size: 11px;
      font-weight: 600;
      padding: 4px 10px;
      border-radius: 12px;
      background: rgba(255, 255, 255, 0.06);
      color: #c9d1d9;
      border: 1px solid rgba(255, 255, 255, 0.08);
      display: inline-flex;
      align-items: center;
      gap: 4px;
    }

    .progress-wrapper {
      margin-bottom: 24px;
    }

    .progress-bar-bg {
      width: 100%;
      height: 6px;
      border-radius: 6px;
      background: rgba(255, 255, 255, 0.08);
      position: relative;
      overflow: hidden;
      cursor: pointer;
    }

    .progress-bar-fill {
      height: 100%;
      width: 0%;
      border-radius: 6px;
      background: linear-gradient(90deg, var(--accent-primary), var(--accent-secondary));
      transition: width 0.3s linear;
      box-shadow: 0 0 10px rgba(0, 242, 254, 0.5);
    }

    .time-labels {
      display: flex;
      justify-content: space-between;
      font-size: 12px;
      font-family: monospace;
      color: var(--text-muted);
      margin-top: 8px;
    }

    .footer-note {
      font-size: 11px;
      color: rgba(139, 148, 158, 0.7);
      margin-top: 20px;
      display: flex;
      align-items: center;
      justify-content: center;
      gap: 6px;
    }
  </style>
</head>
<body>
  <div class="dashboard-container">
    <div class="player-card" id="playerCard">
      <div class="top-bar">
        <span class="brand-tag">DISCORD AUDIO ENGINE</span>
        <div class="status-pill idle" id="statusPill">
          <span class="status-dot"></span>
          <span id="statusText">IDLE</span>
        </div>
      </div>

      <div class="artwork-container">
        <div class="artwork-glow" id="artworkGlow"></div>
        <img src="https://images.unsplash.com/photo-1511671782779-c97d3d27a1d4?auto=format&fit=crop&w=400&q=80" alt="Album Art" class="album-art" id="albumArt">
      </div>

      <div class="equalizer-wave" id="eqWave">
        <div class="eq-bar"></div>
        <div class="eq-bar"></div>
        <div class="eq-bar"></div>
        <div class="eq-bar"></div>
        <div class="eq-bar"></div>
        <div class="eq-bar"></div>
      </div>

      <a href="#" target="_blank" class="track-title" id="trackTitle">No Song Playing</a>
      <div class="track-artist" id="trackArtist">Queue a track in Discord with !play</div>

      <div class="meta-badges">
        <span class="badge" id="sourceBadge">📡 Discord Voice</span>
        <span class="badge" id="speedBadge">⚡ 1.0x</span>
        <span class="badge" id="loopBadge">🔁 Loop: Off</span>
      </div>

      <div class="progress-wrapper">
        <div class="progress-bar-bg">
          <div class="progress-bar-fill" id="progressFill"></div>
        </div>
        <div class="time-labels">
          <span id="currentTime">00:00</span>
          <span id="totalTime">00:00</span>
        </div>
      </div>

      <div class="footer-note">
        <span>⚡ Synchronized in real time with Discord Voice Client</span>
      </div>
    </div>
  </div>

  <script>
    function formatTime(seconds) {
      if (!seconds || seconds < 0) return "00:00";
      const s = Math.floor(seconds);
      const m = Math.floor(s / 60);
      const sec = s % 60;
      return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
    }

    let localPos = 0;
    let duration = 0;
    let isPlaying = false;
    let speed = 1;

    async function fetchState() {
      try {
        const res = await fetch('/api/state');
        if (!res.ok) return;
        const data = await res.json();

        const card = document.getElementById('playerCard');
        const pill = document.getElementById('statusPill');
        const statusText = document.getElementById('statusText');
        const title = document.getElementById('trackTitle');
        const artist = document.getElementById('trackArtist');
        const art = document.getElementById('albumArt');
        const glow = document.getElementById('artworkGlow');
        const eq = document.getElementById('eqWave');
        const sourceBadge = document.getElementById('sourceBadge');
        const speedBadge = document.getElementById('speedBadge');
        const loopBadge = document.getElementById('loopBadge');
        const fill = document.getElementById('progressFill');
        const curTimeLabel = document.getElementById('currentTime');
        const totalTimeLabel = document.getElementById('totalTime');

        isPlaying = data.is_playing && !data.is_paused;
        localPos = data.position || 0;
        duration = data.duration || 0;
        speed = data.speed || 1;

        if (data.is_playing) {
          if (data.is_paused) {
            pill.className = 'status-pill paused';
            statusText.textContent = 'PAUSED';
            eq.className = 'equalizer-wave';
            glow.style.opacity = '0.15';
          } else {
            pill.className = 'status-pill playing';
            statusText.textContent = 'PLAYING';
            eq.className = 'equalizer-wave playing';
            glow.style.opacity = '0.5';
          }
        } else {
          pill.className = 'status-pill idle';
          statusText.textContent = 'IDLE';
          eq.className = 'equalizer-wave';
          glow.style.opacity = '0.1';
        }

        title.textContent = data.title || 'No Song Playing';
        if (data.url) {
          title.href = data.url;
        } else {
          title.removeAttribute('href');
        }

        artist.textContent = data.uploader ? `Artist: ${data.uploader}` : 'Queue a track in Discord with !play';
        if (data.thumbnail) {
          art.src = data.thumbnail;
        }

        sourceBadge.textContent = data.source || '📡 Discord Voice';
        speedBadge.textContent = `⚡ ${data.speed || 1}.0x`;
        loopBadge.textContent = `🔁 Loop: ${(data.loop_mode || 'off').toUpperCase()}`;

        const pct = duration > 0 ? Math.min(100, Math.max(0, (localPos / duration) * 100)) : 0;
        fill.style.width = `${pct}%`;
        curTimeLabel.textContent = formatTime(localPos);
        totalTimeLabel.textContent = formatTime(duration);

      } catch (e) {
        console.error("Failed to fetch state", e);
      }
    }

    // Local progress interpolation between API polls
    setInterval(() => {
      if (isPlaying && duration > 0 && localPos < duration) {
        localPos += 1 * speed;
        const pct = Math.min(100, Math.max(0, (localPos / duration) * 100));
        document.getElementById('progressFill').style.width = `${pct}%`;
        document.getElementById('currentTime').textContent = formatTime(localPos);
      }
    }, 1000);

    fetchState();
    setInterval(fetchState, 3000);
  </script>
</body>
</html>
"""


class HealthHandler(BaseHTTPRequestHandler):
    bot = None

    def do_GET(self):
        url_path = self.path.split("?")[0]

        if url_path in ("/", "/health"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Bot is running")
            return

        if url_path == "/api/state":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Access-Control-Allow-Origin", "*")
            self.end_headers()

            state = {
                "active": False,
                "is_playing": False,
                "is_paused": False,
                "title": None,
                "uploader": None,
                "thumbnail": None,
                "url": None,
                "duration": 0,
                "position": 0.0,
                "speed": 1,
                "loop_mode": "off",
                "source": "Discord Voice",
            }

            if self.bot and hasattr(self.bot, "playback") and self.bot.playback.players:
                # Find first active guild player
                for guild_id, player in self.bot.playback.players.items():
                    if 0 <= player.index < len(player.playlist):
                        item = player.playlist[player.index]
                        title = getattr(item, "title", None) or (item[0] if isinstance(item, (tuple, list)) else str(item))
                        duration = getattr(item, "duration", None) or 0
                        thumbnail = getattr(item, "thumbnail", None)
                        uploader = getattr(item, "uploader", None)
                        url = getattr(item, "url", None)

                        voice = None
                        if player.ctx and player.ctx.guild:
                            voice = player.ctx.guild.voice_client

                        is_playing = bool(voice and voice.is_playing())
                        is_paused = bool(voice and voice.is_paused())

                        src = "Web Audio"
                        if url:
                            if "youtube.com" in url or "youtu.be" in url:
                                src = "🔴 YouTube"
                            elif "soundcloud.com" in url:
                                src = "🟠 SoundCloud"

                        state = {
                            "active": True,
                            "is_playing": is_playing or is_paused,
                            "is_paused": is_paused,
                            "title": title,
                            "uploader": uploader,
                            "thumbnail": thumbnail,
                            "url": url,
                            "duration": duration,
                            "position": player.get_current_position(),
                            "speed": player.speed,
                            "loop_mode": getattr(player, "loop_mode", "off"),
                            "source": src,
                        }
                        break

            self.wfile.write(json.dumps(state).encode("utf-8"))
            return

        if url_path in ("/player", "/dashboard"):
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(PLAYER_HTML.encode("utf-8"))
            return

        self.send_response(404)
        self.end_headers()
        self.wfile.write(b"Not Found")

    def log_message(self, format, *args):
        pass  # keep logs clean


class HealthServer:
    def __init__(self, port: Optional[int] = None, bot=None):
        self.port = port if port is not None else int(os.environ.get("PORT", 8080))
        self.bot = bot
        self.logger = BotLogger("health")

    def start(self):
        bot_ref = self.bot

        class BoundHandler(HealthHandler):
            bot = bot_ref

        server = HTTPServer(("0.0.0.0", self.port), BoundHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        self.logger.info(f"Health & Web Player server listening on port {self.port}")
