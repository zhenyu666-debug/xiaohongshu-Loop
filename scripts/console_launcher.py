"""Unified Console launcher.

A single-window GUI + system tray app that:
  * starts the three FastAPI services (pbp-api 8090, lakehouse-api 8091, xhs-saas 8080)
    as local subprocesses (uvicorn), no Docker required.
  * waits until every service answers /healthz before reporting 'ready'.
  * optionally opens http://127.0.0.1:8080/console/ in the user's browser.
  * tails stdout/stderr of each service into the in-window log panel.
  * exposes Stop / Start / Open Console / Quit buttons.
  * shrinks to system tray instead of quitting when the window is closed.

Designed to be run as ``python scripts/console_launcher.py`` and bundled
into a single ``.exe`` via ``pyinstaller`` (see ``scripts/build_launcher.py``).
"""

from __future__ import annotations

import os
import queue
import socket
import struct
import subprocess
import sys
import threading
import time
import tkinter as tk
import urllib.request
import webbrowser
import zlib
from dataclasses import dataclass
from pathlib import Path
from tkinter import scrolledtext, ttk
from typing import Optional

APP_TITLE = "xhs-saas Unified Console"

REPO_ROOT = Path(__file__).resolve().parent.parent

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


def _png_icon_bytes() -> bytes:
    """Build a tiny in-memory PNG icon (32x32, slate disc + green centre)."""
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


def _port_open(host: str, port: int, timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _http_get(url: str, timeout: float = 1.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            return 200 <= resp.status < 500
    except Exception:
        return False


@dataclass
class ServiceState:
    cfg: dict
    proc: Optional[subprocess.Popen] = None
    healthy: bool = False
    started_at: Optional[float] = None
    last_error: str = ""


class ConsoleLauncher:
    def __init__(self) -> None:
        self.states: dict = {s["name"]: ServiceState(cfg=s) for s in SERVICES}
        self.log_q: "queue.Queue[tuple[str, str]]" = queue.Queue()
        self._stopping = False
        self._supervisor: Optional[threading.Thread] = None
        self._tray_icon = None

        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry("780x520")
        self.root.minsize(640, 380)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        try:
            self.root.iconphoto(True, tk.PhotoImage(data=_png_icon_bytes()))
        except Exception:
            pass

        self._build_ui()
        self._poll_log_queue()
        self._refresh_status()

    # ---------------- UI ----------------
    def _build_ui(self) -> None:
        bg = "#0f172a"
        card = "#111827"
        fg = "#e2e8f0"
        muted = "#94a3b8"
        accent = "#22c55e"

        self.root.configure(bg=bg)
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure("TFrame", background=bg)
        style.configure("Card.TFrame", background=card)
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("Card.TLabel", background=card, foreground=fg)
        style.configure("Muted.TLabel", background=bg, foreground=muted)
        style.configure(
            "Accent.TButton",
            background=accent,
            foreground="#052e16",
            padding=(14, 8),
            font=("Segoe UI", 10, "bold"),
        )
        style.configure("TButton", background="#1f2937", foreground=fg, padding=(10, 8))
        style.map("Accent.TButton", background=[("active", "#16a34a")])
        style.map("TButton", background=[("active", "#374151")])

        header = ttk.Frame(self.root, padding=(16, 14))
        header.pack(fill="x")
        ttk.Label(
            header,
            text=APP_TITLE,
            font=("Segoe UI", 14, "bold"),
            foreground=fg,
        ).pack(side="left")
        ttk.Label(
            header,
            text="Start the three services, then auto-open the unified console.",
            style="Muted.TLabel",
        ).pack(side="left", padx=12)

        status_card = ttk.Frame(self.root, style="Card.TFrame", padding=14)
        status_card.pack(fill="x", padx=16, pady=(0, 12))

        self.status_labels: dict = {}
        for svc in SERVICES:
            row = ttk.Frame(status_card, style="Card.TFrame")
            row.pack(fill="x", pady=2)
            swatch = tk.Label(row, bg=svc["color"], width=2)
            swatch.pack(side="left", padx=(0, 8))
            name_lbl = ttk.Label(
                row,
                text=f'{svc["name"]}  ',
                width=14,
                style="Card.TLabel",
                font=("Consolas", 10, "bold"),
            )
            name_lbl.pack(side="left")
            ttk.Label(
                row,
                text=f'port {svc["port"]}',
                style="Card.TLabel",
                foreground=muted,
            ).pack(side="left")
            state_lbl = tk.Label(
                row,
                text="* stopped",
                bg=card,
                fg="#94a3b8",
                font=("Segoe UI", 10, "bold"),
            )
            state_lbl.pack(side="right")
            self.status_labels[svc["name"]] = {"state": state_lbl, "swatch": swatch}

        btnbar = ttk.Frame(self.root, padding=(16, 0))
        btnbar.pack(fill="x", pady=(0, 10))
        self.start_btn = ttk.Button(
            btnbar,
            text="Start services",
            style="Accent.TButton",
            command=self.start_all,
        )
        self.start_btn.pack(side="left", padx=(0, 8))
        self.open_btn = ttk.Button(
            btnbar, text="Open console", command=self.open_console, state="disabled"
        )
        self.open_btn.pack(side="left", padx=(0, 8))
        self.stop_btn = ttk.Button(
            btnbar, text="Stop services", command=self.stop_all, state="disabled"
        )
        self.stop_btn.pack(side="left", padx=(0, 8))
        ttk.Button(btnbar, text="Copy URL", command=self.copy_url).pack(side="left")
        ttk.Button(btnbar, text="Quit", command=self._quit).pack(side="right")

        log_frame = ttk.Frame(self.root, padding=(16, 0))
        log_frame.pack(fill="both", expand=True, pady=(0, 12))
        ttk.Label(log_frame, text="Logs (stdout / stderr)", style="Muted.TLabel").pack(
            anchor="w"
        )
        self.log = scrolledtext.ScrolledText(
            log_frame,
            height=12,
            bg="#020617",
            fg="#cbd5f5",
            insertbackground=fg,
            font=("Consolas", 9),
            borderwidth=0,
            relief="flat",
        )
        self.log.pack(fill="both", expand=True, pady=(6, 0))
        for svc in SERVICES:
            self.log.tag_configure(svc["name"], foreground=svc["color"])
        self.log.tag_configure("sys", foreground="#facc15")

        footer = ttk.Frame(self.root, padding=(16, 8))
        footer.pack(fill="x")
        self.footer_lbl = ttk.Label(
            footer,
            text="Ready. Click Start to launch the three services.",
            style="Muted.TLabel",
        )
        self.footer_lbl.pack(side="left")

    # ---------------- Logging ----------------
    def _log(self, tag: str, msg: str) -> None:
        self.log_q.put((tag, msg))

    def _poll_log_queue(self) -> None:
        try:
            while True:
                tag, msg = self.log_q.get_nowait()
                ts = time.strftime("%H:%M:%S")
                self.log.insert("end", f"[{ts}] {msg}\n", tag)
        except queue.Empty:
            pass
        self.log.see("end")
        self.root.after(120, self._poll_log_queue)

    def _reader_thread(self, name: str, stream) -> None:
        for raw in iter(stream.readline, b""):
            try:
                line = raw.decode("utf-8", errors="replace").rstrip()
            except Exception:
                continue
            if line:
                self._log(name, line)
        stream.close()

    # ---------------- Lifecycle ----------------
    def start_all(self) -> None:
        if any(st.proc and st.proc.poll() is None for st in self.states.values()):
            self._log("sys", "Services already running.")
            return
        self._log("sys", "Starting three services (uvicorn, local)...")
        for svc in SERVICES:
            self._spawn(svc["name"])
        self.start_btn.configure(state="disabled")
        self.stop_btn.configure(state="normal")
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
            self._log("sys", f"[{name}] failed to spawn: {e}")
            return
        st.proc = proc
        st.started_at = time.time()
        st.last_error = ""
        self._log("sys", f"[{name}] spawned pid={proc.pid} on port {cfg['port']}")
        threading.Thread(
            target=self._reader_thread, args=(name, proc.stdout), daemon=True
        ).start()

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
                    self._log("sys", f"[{svc['name']}] healthy at {url}")
                st.healthy = ok
            ready = all(self.states[s["name"]].healthy for s in SERVICES)
            if ready and not all_ready_logged:
                all_ready_logged = True
                self._log("sys", "All three services are healthy.")
            elif not ready:
                all_ready_logged = False
            self.root.after(0, self._refresh_status)
            time.sleep(1.5)

    def _refresh_status(self) -> None:
        any_alive = False
        all_healthy = True
        for svc in SERVICES:
            st = self.states[svc["name"]]
            lbl = self.status_labels[svc["name"]]["state"]
            swatch = self.status_labels[svc["name"]]["swatch"]
            if st.proc is None or st.proc.poll() is not None:
                text, color = "* stopped", "#94a3b8"
            elif st.healthy:
                text, color = "* healthy", "#22c55e"
                any_alive = True
            else:
                text, color = "* starting...", "#facc15"
                any_alive = True
                all_healthy = False
            lbl.configure(text=text, fg=color)
            if st.proc is None:
                swatch.configure(bg="#475569")
            elif st.healthy:
                swatch.configure(bg="#22c55e")
            else:
                swatch.configure(bg=svc["color"])
        if all_healthy and any_alive:
            self.footer_lbl.configure(text=f"All services healthy.   Open: {CONSOLE_URL}")
            self.open_btn.configure(state="normal")
        elif any_alive:
            self.footer_lbl.configure(text="Starting services, please wait...")
        else:
            self.footer_lbl.configure(text="Ready. Click Start to launch the three services.")

    def open_console(self) -> None:
        if not _http_get(CONSOLE_URL, timeout=1.0):
            self._log("sys", f"Console not ready yet: {CONSOLE_URL}")
            return
        webbrowser.open(CONSOLE_URL)
        self._log("sys", f"Opened {CONSOLE_URL} in default browser.")

    def copy_url(self) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(CONSOLE_URL)
        self._log("sys", f"Copied {CONSOLE_URL} to clipboard.")

    def stop_all(self) -> None:
        self._log("sys", "Stopping services...")
        self._stopping = True
        for st in self.states.values():
            self._terminate(st.proc)
            st.proc = None
            st.healthy = False
        self._stopping = False
        self.start_btn.configure(state="normal")
        self.stop_btn.configure(state="disabled")
        self.open_btn.configure(state="disabled")
        self._refresh_status()
        self._log("sys", "All services stopped.")

    @staticmethod
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

    def _on_close(self) -> None:
        if self._stopping:
            return
        try:
            import pystray
            from PIL import Image
            from io import BytesIO

            img = Image.open(BytesIO(_png_icon_bytes()))
            menu = pystray.Menu(
                pystray.MenuItem(
                    "Show window", lambda _i, _t: self.root.after(0, self._deiconify)
                ),
                pystray.MenuItem("Open console", lambda _i, _t: self.open_console()),
                pystray.MenuItem("Stop services", lambda _i, _t: self.stop_all()),
                pystray.MenuItem("Quit", lambda _i, _t: self._quit()),
            )
            self._tray_icon = pystray.Icon("xhs-saas", img, APP_TITLE, menu)
            self.root.withdraw()
            threading.Thread(target=self._tray_icon.run, daemon=True).start()
            self._log("sys", "Window hidden to system tray.")
        except Exception as e:
            self._log("sys", f"Tray unavailable ({e}); quitting instead.")
            self._quit()

    def _deiconify(self) -> None:
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()

    def _quit(self) -> None:
        self.stop_all()
        try:
            if getattr(self, "_tray_icon", None):
                self._tray_icon.stop()
        except Exception:
            pass
        try:
            self.root.destroy()
        except tk.TclError:
            pass
        sys.exit(0)

    def run(self) -> None:
        self.root.mainloop()


def main() -> int:
    try:
        ConsoleLauncher().run()
    except KeyboardInterrupt:
        return 130
    return 0


if __name__ == "__main__":
    sys.exit(main())
