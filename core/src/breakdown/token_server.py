from __future__ import annotations

import json
import socket
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from loguru import logger

from breakdown.config import Settings


def find_free_port(start: int) -> int:
    port = start
    while port < 65535:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("127.0.0.1", port))
                return port
        except OSError:
            port += 1
    raise RuntimeError(f"No free port found starting from {start}")


def write_runtime_info(port: int, livekit_url: str, breakdown_dir: Path) -> None:
    breakdown_dir.mkdir(parents=True, exist_ok=True)
    tmp = breakdown_dir / "runtime.json.tmp"
    tmp.write_text(json.dumps({"port": port, "livekit_url": livekit_url}))
    tmp.replace(breakdown_dir / "runtime.json")


def _make_token(api_key: str, api_secret: str, room: str) -> str:
    from livekit.api import AccessToken, VideoGrants  # type: ignore[import-untyped]
    token = (
        AccessToken(api_key, api_secret)
        .with_identity("agent")
        .with_grants(VideoGrants(room_join=True, room=room))
        .to_jwt()
    )
    return str(token)


class TokenServer:
    def __init__(self, settings: Settings, breakdown_dir: Path) -> None:
        self._settings = settings
        self._breakdown_dir = breakdown_dir

    def start(self, port: int | None = None) -> None:
        if port is None:
            port = find_free_port(self._settings.token_server_port_start)
        write_runtime_info(port, self._settings.livekit_url, self._breakdown_dir)

        settings = self._settings

        class _Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                parsed = urlparse(self.path)
                if parsed.path != "/token":
                    self.send_response(404)
                    self.end_headers()
                    return
                params = parse_qs(parsed.query)
                room = params.get("room", ["default"])[0]
                try:
                    token = _make_token(
                        settings.livekit_api_key,
                        settings.livekit_api_secret,
                        room,
                    )
                    body = json.dumps({"token": token, "url": settings.livekit_url}).encode()
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except Exception as e:
                    logger.error("Token generation failed: {}", e)
                    self.send_response(500)
                    self.end_headers()

            def log_message(self, format: str, *args: object) -> None:
                logger.debug("token_server: " + format, *args)

        server = HTTPServer(("127.0.0.1", port), _Handler)
        logger.info("Token server listening on 127.0.0.1:{}", port)
        server.serve_forever()

    def start_background(self, port: int | None = None) -> threading.Thread:
        t = threading.Thread(target=self.start, kwargs={"port": port}, daemon=True)
        t.start()
        return t
