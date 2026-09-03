"""Tiny HTTP server: Render free web services require a bound port, and this
doubles as the health-check endpoint that keeps the service alive."""

import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer


class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Bot is running")

    def log_message(self, format, *args):
        pass  # keep logs clean


class HealthServer:
    def __init__(self, port: int | None = None):
        self.port = port if port is not None else int(os.environ.get("PORT", 8080))

    def start(self):
        server = HTTPServer(("0.0.0.0", self.port), HealthHandler)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        print(f"Health server listening on port {self.port}")
