"""Unified Console tray launcher.

A tiny pystray-only controller that:
  * shows a system-tray icon with a menu (Start / Stop / Open console / Quit)
  * starts the three FastAPI services (pbp-api 8090, lakehouse-api 8091,
    xhs-saas 8080) as local subprocesses (uvicorn), no Docker required
  * polls every service's /healthz until they are all healthy
  * exposes a small HTTP status endpoint on 127.0.0.1:8765 so other
    front-ends (cmd, PowerShell, the console itself) can introspect state
  * writes its log to ``./logs/launcher.log`` (also visible via the menu)

Designed to be run as ``python scripts/tray_launcher.py`` and bundled
into a single ``.exe`` via ``pyinstaller``.

Why tray-only?  Tkinter is not guaranteed to be installed in minimal
CPython distributions on Windows.  ``pystray`` + ``Pillow`` ship as
pure-Python wheels and work everywhere.
"""

from __future__ import annotations

import json
import os
import queue
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
import zlib
import struct
from dataclasses import dataclass, field
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

APP_NAME = "xhs-saas Unified Console"

REPO_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = REPO_ROOT / "logs"
LOG_PATH = LOG_DIR / "launcher.log"
STATUS_HOST = "127.0.0.1"
STATUS_PORT = 8765

SERVICES = [
    {
        "name": "pbp-api",
        "cwd": REPO_ROOT / "donor-screener-pbp",
        "module": "pbp_api.main:app",
        "port": 8090,
        "color": "#38bdf8",
    },
    {
        "name": "lakehouse-api",
        "cwd": REPO_ROOT / "data-lakehouse",
        "module": "lakehouse_api.main:app",
        "port": 8091,
        "color": "#a78bfa",
    },
    {
        "name": "xhs-saas",
        "cwd": REPO_ROOT / "xiaohongshu-saas",
        "module": "app.main:app",
        "port": 8080,
        "color": "#34d399",
    },
]

CONSOLE_URL = "http://127.0.0.1:8080/console/"


# ---------------------------------------------------------------------------
# PNG icon (32x32, slate disc + green centre)
# ---------------------------------------------------------------------------
def _png_icon_bytes() -> bytes:
    w = h = 32
    pixels = bytearray()
    for _y in range(h):
        pixels.append(0)
        for x in range(w):
            cx, cy = w / 2 - 0.5, h / 2 - 0.5
            r = ((x - cx) ** 2 + (_y - cy) ** 2) ** 0.5
            if r <= 5:
                pixels += bytes((34, 197, 94, 255))
            elif r <= 9:
                pixels += bytes((30, 41, 59, 255))
            elif r <= 14:
                pixels += bytes((15, 23, 42, 255))
            else:
                pixels += bytes((0, 0, 0, 0))
    raw = b"".join(b"\x00" + bytes(pixels[_y * w * 4:(_y + 1) * w * 4]) for _y in range(h))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return (
            struct.pack(">I", len(data))
            + tag
            + data
            + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
        )

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    idat = zlib.compress(raw)
    return signature + chunk(b"IHDR", ihdr) + chunk(b"IDAT", idat) + chunk(b"IEND", b"")


# ---------------------------------------------------------------------------
# Subprocess helpers
# ---------------------------------------------------------------------------
def _http_get(url: str, timeout: float = 0.6) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return 200 <= resp.status < 500
    except Exception:
        return False


def _terminate(proc: Optional[subprocess.Popen]) -> None:
    if not proc or proc.poll() is not None:
        return
    try:
        proc.terminate()
        try:
            proc.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=2.0)
    except Exception as e:
        print(f"terminate error: {e}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Application state
# ---------------------------------------------------------------------------
@dataclass
class ServiceState:
    cfg: dict
    proc: Optional[subprocess.Popen] = None
    healthy: bool = False
    started_at: Optional[float] = None
    last_error: str = ""


class Launcher:
    def __init__(self) -> None:
        self.states: dict = {s["name"]: ServiceState(cfg=s) for s in SERVICES}
        self._stopping = False
        self._supervisor: Optional[threading.Thread] = None
        self._status_server: Optional[ThreadingHTTPServer] = None
        self._status_thread: Optional[threading.Thread] = None
        self._log_lock = threading.Lock()
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    # ---------------- logging ----------------
    def _log(self, msg: str) -> None:
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] {msg}"
        print(line, flush=True)
        with self._log_lock:
            try:
                with LOG_PATH.open("a", encoding="utf-8") as f:
                    f.write(line + "\n")
            except Exception:
                pass

    # ---------------- lifecycle ----------------
    def start_all(self, icon=None) -> None:
        if any(st.proc and st.proc.poll() is None for st in self.states.values()):
            self._log("Services already running.")
            return
        self._log("Starting three services (uvicorn, local)...")
        for svc in SERVICES:
            self._spawn(svc["name"])
        if self._supervisor is None or not self._supervisor.is_alive():
            self._supervisor = threading.Thread(target=self._supervise, daemon=True)
            self._supervisor.start()

    def _spawn(self, name: str) -> None:
        st = self.states[name]
        if st.proc and st.proc.poll() is None:
            return
        cfg = st.cfg
        env = os.environ.copy()
        env["PYTHONUNBUFFERED"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        env["APP_HOST"] = "127.0.0.1"
        env["APP_PORT"] = str(cfg["port"])
        env["PBP_API_URL"] = "http://127.0.0.1:8090"
        env["LAKEHOUSE_API_URL"] = "http://127.0.0.1:8091"
        try:
            proc = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "uvicorn",
                    cfg["module"],
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(cfg["port"]),
                    "--log-level",
                    "info",
                ],
                cwd=str(cfg["cwd"]),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except FileNotFoundError as e:
            st.last_error = f"spawn failed: {e}"
            self._log(f"[{name}] failed to spawn: {e}")
            return
        st.proc = proc
        st.started_at = time.time()
        st.last_error = ""
        self._log(f"[{name}] spawned pid={proc.pid} on port {cfg['port']}")
        threading.Thread(target=self._reader_thread, args=(name, proc.stdout), daemon=True).start()

    def _reader_thread(self, name: str, stream) -> None:
        for raw in iter(stream.readline, b""):
            try:
                line = raw.decode("utf-8", errors="replace").rstrip()
            except Exception:
                continue
            if line:
                self._log(f"[{name}] {line}")
        stream.close()

    def _supervise(self) -> None:
        all_ready_logged = False
        while not self._stopping:
            for svc in SERVICES:
                st = self.states[svc["name"]]
                if not st.proc:
                    st.healthy = False
                    continue
                if st.proc.poll() is not None:
                    st.healthy = False
                    st.last_error = f"exited with code {st.proc.returncode}"
                    continue
                url = f"http://127.0.0.1:{svc['port']}/healthz"
                ok = _http_get(url, timeout=0.6)
                if ok and not st.healthy:
                    self._log(f"[{svc['name']}] healthy at {url}")
                st.healthy = ok
            ready = all(self.states[s["name"]].healthy for s in SERVICES)
            if ready and not all_ready_logged:
                all_ready_logged = True
                self._log("All three services are healthy.")
                self._log(f"Console URL: {CONSOLE_URL}")
            elif not ready:
                all_ready_logged = False
            time.sleep(1.5)

    def stop_all(self, icon=None) -> None:
        self._log("Stopping services...")
        self._stopping = True
        for st in self.states.values():
            _terminate(st.proc)
            st.proc = None
            st.healthy = False
        self._stopping = False
        self._log("All services stopped.")

    # ---------------- status snapshot ----------------
    def snapshot(self) -> dict:
        out: dict = {
            "console_url": CONSOLE_URL,
            "all_healthy": False,
            "services": {},
        }
        all_healthy = True
        any_proc = False
        for svc in SERVICES:
            st = self.states[svc["name"]]
            running = bool(st.proc and st.proc.poll() is None)
            if running:
                any_proc = True
            if not st.healthy:
                all_healthy = False
            out["services"][svc["name"]] = {
                "port": svc["port"],
                "running": running,
                "healthy": st.healthy,
                "last_error": st.last_error,
            }
        out["all_healthy"] = all_healthy and any_proc
        return out

    # ---------------- status HTTP server ----------------
    def start_status_server(self) -> None:
        launcher = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args) -> None:  # silence stderr noise
                pass

            def do_GET(self) -> None:  # noqa: N802
                if self.path in ("/", "/status"):
                    body = json.dumps(launcher.snapshot(), indent=2).encode("utf-8")
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                    return
                self.send_response(404)
                self.end_headers()

        try:
            self._status_server = ThreadingHTTPServer((STATUS_HOST, STATUS_PORT), Handler)
        except OSError as e:
            self._log(f"Status server failed to bind {STATUS_HOST}:{STATUS_PORT}: {e}")
            return
        self._status_thread = threading.Thread(
            target=self._status_server.serve_forever, daemon=True
        )
        self._status_thread.start()
        self._log(f"Status server: http://{STATUS_HOST}:{STATUS_PORT}/status")

    # ---------------- tray actions ----------------
    def open_console(self, _icon=None, _item=None) -> None:
        if _http_get(CONSOLE_URL, timeout=1.0):
            webbrowser.open(CONSOLE_URL)
            self._log(f"Opened {CONSOLE_URL} in default browser.")
        else:
            self._log(f"Console not ready yet: {CONSOLE_URL}")

    def open_status(self, _icon=None, _item=None) -> None:
        url = f"http://{STATUS_HOST}:{STATUS_PORT}/status"
        webbrowser.open(url)
        self._log(f"Opened status page: {url}")

    def open_logs(self, _icon=None, _item=None) -> None:
        try:
            if os.name == "nt":
                os.startfile(str(LOG_PATH))  # type: ignore[attr-defined]
            else:
                webbrowser.open(f"file://{LOG_PATH}")
        except Exception as e:
            self._log(f"Failed to open log: {e}")

    def quit_app(self, icon, _item=None) -> None:
        self.stop_all()
        try:
            if self._status_server:
                self._status_server.shutdown()
        except Exception:
            pass
        try:
            icon.stop()
        except Exception:
            pass
        sys.exit(0)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> int:
    launcher = Launcher()
    launcher._log(f"{APP_NAME} starting up...")
    launcher.start_status_server()

    import pystray
    from PIL import Image
    from io import BytesIO

    img = Image.open(BytesIO(_png_icon_bytes()))

    def label_start(_i, item): return "Start services (already running)" if any(
        st.proc and st.proc.poll() is None for st in launcher.states.values()
    ) else "Start services"

    def label_stop(_i, item): return "Stop services (idle)" if not any(
        st.proc and st.proc.poll() is None for st in launcher.states.values()
    ) else "Stop services"

    menu = pystray.Menu(
        pystray.MenuItem(label_start, launcher.start_all),
        pystray.MenuItem(label_stop, launcher.stop_all),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Open console in browser", launcher.open_console),
        pystray.MenuItem("Show status JSON", launcher.open_status),
        pystray.MenuItem("Open log file", launcher.open_logs),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(f"Log: {LOG_PATH}", None, enabled=False),
        pystray.MenuItem(f"Status: http://{STATUS_HOST}:{STATUS_PORT}/status", None, enabled=False),
        pystray.MenuItem("Quit", launcher.quit_app),
    )

    icon = pystray.Icon(
        "xhs-saas",
        img,
        APP_NAME,
        menu,
    )

    def on_activate(_icon, _item) -> None:
        launcher.open_console()

    icon.default_action = on_activate

    launcher._log(
        f"{APP_NAME} ready.  Right-click the tray icon for the menu, "
        f"double-click it to open the console."
    )
    icon.run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
