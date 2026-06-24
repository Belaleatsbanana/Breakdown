from __future__ import annotations

import json
import socket
import threading
import time
from pathlib import Path

import httpx
import pytest

from breakdown.config import Settings
from breakdown.token_server import TokenServer, find_free_port, write_runtime_info


def test_find_free_port_returns_usable_port() -> None:
    port = find_free_port(7890)
    assert 7890 <= port <= 65535
    # verify it is actually free
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", port))


def test_write_runtime_info(tmp_path: Path) -> None:
    write_runtime_info(7890, "ws://localhost:7880", tmp_path)
    data = json.loads((tmp_path / "runtime.json").read_text())
    assert data["port"] == 7890
    assert data["livekit_url"] == "ws://localhost:7880"


def test_token_server_responds_to_token_request(tmp_path: Path) -> None:
    settings = Settings(
        livekit_api_key="devkey",
        livekit_api_secret="devsecret123456789012345678901234567890",
        livekit_url="ws://localhost:7880",
    )
    server = TokenServer(settings=settings, breakdown_dir=tmp_path)
    port = find_free_port(7891)
    thread = threading.Thread(target=server.start, kwargs={"port": port}, daemon=True)
    thread.start()
    time.sleep(0.1)  # let the server bind

    response = httpx.get(f"http://127.0.0.1:{port}/token?room=test-room", timeout=2)
    assert response.status_code == 200
    data = response.json()
    assert "token" in data
    assert "url" in data
