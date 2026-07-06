"""Unified Console desktop launcher (GUI).

A real Windows GUI window (pywebview + system HTML/CSS) that:
  * shows live status of the three FastAPI services (pbp-api 8090,
    lakehouse-api 8091, xhs-saas 8080) and a rolling log tail
  * starts them as local uvicorn subprocesses (no Docker required)
  * adds a Windows system-tray icon with the same Start / Stop / Quit menu
  * exposes a status server on 127.0.0.1:8765 for scripting/automation

Run as ``python scripts/console_gui.py`` or build a single ``.exe`` via
``pyinstaller`` (see ``scripts/build_launcher.py``).

Why pywebview and not Tkinter?  Tkinter is not guaranteed to be installed
in minimal CPython distributions on Windows.  pywebview uses the
already-installed WebView2 runtime (Win10/11 default), ships as a pure-
Python wheel, and gives us proper HTML/CSS rendering - exactly the
"Unified Console" experience the project is aiming for.
"""

from __future__ import annotations

import json
import os
import queue
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
import zlib
import struct
from dataclasses import dataclass
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Optional

APP_NAME = "小红书 SaaS 一体化控制台"
APP_VERSION = "0.1.0"

REPO_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = REPO_ROOT / "logs"
LOG_PATH = LOG_DIR / "launcher.log"
STATUS_HOST = "127.0.0.1"
STATUS_PORT = 8765
LOCAL_GUI_PORT = 8766

SERVICES = [
    {
        "name": "xhs-saas",
        "enabled": True,
        "cwd": REPO_ROOT / "xiaohongshu-saas",
        "module": "app.main:app",
        "port": 8080,
        "color": "#34d399",
        "label": "小红书 SaaS · 网关 + 控制台宿主",
    },
    {
        "name": "pbp-api",
        "enabled": False,  # donor-screener-pbp source moved to private repo (CHANGELOG 0.6.1);
                            # this slot is reserved for when the standalone exe becomes available.
                            # Leave disabled: spawning it would ModuleNotFoundError on every restart.
        "cwd": REPO_ROOT / "donor-screener-pbp",
        "module": "pbp_api.main:app",
        "port": 8090,
        "color": "#38bdf8",
        "label": "供体筛选服务 · 候选分子 API（暂未启用）",
    },
    {
        "name": "lakehouse-api",
        "enabled": False,  # data-lakehouse source moved to private repo (CHANGELOG 0.6.1);
                            # same story as pbp-api above.
        "cwd": REPO_ROOT / "data-lakehouse",
        "module": "lakehouse_api.main:app",
        "port": 8091,
        "color": "#a78bfa",
        "label": "数据湖仓 · 分析指标 API（暂未启用）",
    },
]

CONSOLE_URL = "http://127.0.0.1:8080/console/"


# ---------------------------------------------------------------------------
# Tiny PNG tray icon (32x32, slate disc + green centre)
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
# Helpers
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
    except Exception:
        pass


# ---------------------------------------------------------------------------
# HTML / CSS / JS served to the pywebview window
# ---------------------------------------------------------------------------
GUI_HTML = r"""<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8" />
<title>__APP_NAME__</title>
<style>
  :root {
    color-scheme: dark;
    --bg: #0b1120;
    --bg-2: #111c2f;
    --card: #131e35;
    --border: #1f2a44;
    --fg: #e2e8f0;
    --muted: #94a3b8;
    --accent: #22c55e;
    --warn: #facc15;
    --danger: #ef4444;
    --info: #38bdf8;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    font-family: "Segoe UI", "Inter", -apple-system, sans-serif;
    background: linear-gradient(180deg, #0a1020 0%, #060912 100%);
    color: var(--fg);
    min-height: 100vh;
    overflow: hidden;
  }
  header {
    padding: 14px 18px;
    border-bottom: 1px solid var(--border);
    display: flex; align-items: center; justify-content: space-between;
    background: rgba(10,16,32,0.85);
    backdrop-filter: blur(8px);
  }
  header h1 { margin: 0; font-size: 14px; font-weight: 600; }
  header .ver { color: var(--muted); font-size: 11px; }
  .pill {
    padding: 2px 8px; border-radius: 999px;
    background: var(--bg-2); border: 1px solid var(--border);
    font-size: 11px; color: var(--muted);
  }
  main {
    display: grid;
    grid-template-rows: auto 1fr;
    gap: 12px;
    padding: 14px 16px;
    height: calc(100vh - 56px);
  }
  .toolbar {
    display: flex; gap: 8px; flex-wrap: wrap;
  }
  button {
    background: #1f2937;
    color: var(--fg);
    border: 1px solid #2a3a55;
    border-radius: 6px;
    padding: 8px 14px;
    font-size: 12px;
    font-weight: 600;
    cursor: pointer;
    transition: background 120ms, transform 80ms;
  }
  button:hover:not(:disabled) { background: #2a3a55; }
  button:active:not(:disabled) { transform: translateY(1px); }
  button:disabled { opacity: 0.45; cursor: not-allowed; }
  .primary {
    background: var(--accent); color: #052e16; border-color: #16a34a;
  }
  .primary:hover:not(:disabled) { background: #16a34a; color: #052e16; }
  .danger {
    background: #b91c1c; color: #fff; border-color: #ef4444;
  }
  .danger:hover:not(:disabled) { background: #ef4444; }
  .grid {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 10px;
  }
  .card {
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 10px;
    padding: 12px;
    display: flex; flex-direction: column; gap: 6px;
  }
  .card-head { display: flex; justify-content: space-between; align-items: center; }
  .swatch { width: 10px; height: 10px; border-radius: 50%; }
  .name { font-weight: 700; font-family: Consolas, monospace; font-size: 13px; }
  .desc { color: var(--muted); font-size: 11px; min-height: 14px; }
  .meta { font-size: 11px; color: var(--muted); }
  .state {
    font-weight: 700; font-size: 11px; padding: 3px 8px;
    border-radius: 999px; display: inline-block;
  }
  .state.stopped { background: #1e293b; color: var(--muted); }
  .state.starting { background: #422006; color: var(--warn); }
  .state.healthy { background: #052e16; color: var(--accent); }
  .state.error { background: #450a0a; color: var(--danger); }
  .state.disabled {
    background: #1a1f2e; color: var(--muted);
    border: 1px dashed #334155;
  }
  .card.disabled-card {
    opacity: 0.55;
    background: #0e1626;
    border-style: dashed;
  }
  pre.log {
    margin: 0; background: #020617;
    color: #cbd5f5; font-family: Consolas, monospace; font-size: 11px;
    padding: 8px; border-radius: 8px; border: 1px solid var(--border);
    height: 100%; overflow: auto; white-space: pre-wrap;
  }
  .log .err { color: #fca5a5; }
  .log .sys { color: var(--warn); }
  .log .s-pbp   { color: #38bdf8; }
  .log .s-lake  { color: #a78bfa; }
  .log .s-xhs   { color: #34d399; }
  .footer {
    text-align: center; color: var(--muted); font-size: 11px;
    padding: 4px 0 12px;
  }
  .footer a { color: var(--info); text-decoration: none; }
  .footer a:hover { text-decoration: underline; }
  a.btn-link { text-decoration: none; }
</style>
</head>
<body>
<header>
  <h1>__APP_NAME__</h1>
  <div>
    <span class="pill" id="overall">状态：等待启动</span>
    <span class="pill">v__APP_VERSION__</span>
  </div>
</header>

<main>
  <div class="toolbar">
    <button id="b-start"  class="primary">启动服务</button>
    <button id="b-stop"   class="danger"  disabled>停止服务</button>
    <button id="b-open"                    disabled>在浏览器中打开控制台</button>
    <button id="b-status">查看状态 JSON</button>
    <button id="b-logs">打开日志文件</button>
    <button id="b-quit" class="danger">退出</button>
  </div>

  <div class="grid" id="cards">
    __SERVICE_CARDS__
  </div>

  <pre class="log" id="log"></pre>
</main>

<div class="footer">
  健康后可访问控制台：
  <a id="url" href="#" class="btn-link">__CONSOLE_URL__</a>
  &nbsp;|&nbsp;
  状态端点：<a href="http://__STATUS_HOST__:__STATUS_PORT__/status" target="_blank">http://__STATUS_HOST__:__STATUS_PORT__/status</a>
</div>

<script>
  const urlEl = document.getElementById('url');
  urlEl.addEventListener('click', (e) => { e.preventDefault(); pywebview.api.open_console(); });
  document.getElementById('b-start').onclick  = () => pywebview.api.start_all();
  document.getElementById('b-stop').onclick   = () => pywebview.api.stop_all();
  document.getElementById('b-open').onclick   = () => pywebview.api.open_console();
  document.getElementById('b-status').onclick = () => pywebview.api.open_status();
  document.getElementById('b-logs').onclick   = () => pywebview.api.open_logs();
  document.getElementById('b-quit').onclick   = () => pywebview.api.quit_app();

  const cardEls = __CARD_INDEX__;
  function escapeHtml(s) {
    return (s ?? '').toString()
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }
  function setState(name, kind, msg) {
    const card = cardEls[name];
    if (!card) return;
    card.state.className = 'state ' + kind;
    card.state.textContent = msg;
    card.swatch.style.background = (kind === 'healthy') ? '#22c55e'
      : (kind === 'error') ? '#ef4444'
      : (kind === 'starting') ? '#facc15' : '#475569';
    card.meta.textContent = '端口 ' + card.port;
  }
  function appendLog(line, cls) {
    const el = document.getElementById('log');
    el.insertAdjacentHTML('beforeend',
      '<span class="' + (cls || '') + '">' + escapeHtml(line) + '</span>\n');
    el.scrollTop = el.scrollHeight;
    // cap rendered lines at 500
    while (el.childNodes.length > 500) el.removeChild(el.firstChild);
  }
  window.updateState = (payload) => {
    const data = JSON.parse(payload);
    const order = ['xhs-saas', 'pbp-api', 'lakehouse-api'];
    let anyAlive = false; let allHealthy = true;
    for (const n of order) {
      const sv = data.services[n];
      const card = cardEls[n];
      if (!card) continue;
      let kind, msg;
      if (sv.state === 'disabled') {
        kind = 'disabled'; msg = '○ 未启用';
        if (card.el) card.el.classList.add('disabled-card');
      } else {
        if (card.el) card.el.classList.remove('disabled-card');
        if (!sv.running) { kind = 'stopped'; msg = '● 已停止'; allHealthy = false; }
        else if (sv.healthy) { kind = 'healthy'; msg = '● 健康'; anyAlive = true; }
        else { kind = 'starting'; msg = '● 启动中…'; anyAlive = true; allHealthy = false; }
      }
      setState(n, kind, msg);
    }
    document.getElementById('overall').textContent =
      !anyAlive ? '状态：空闲'
      : (allHealthy ? '状态：全部健康' : '状态：启动中');
    document.getElementById('b-start').disabled = anyAlive;
    document.getElementById('b-stop').disabled = !anyAlive;
    document.getElementById('b-open').disabled = !allHealthy;
  };
  window.appendLog = (line, cls) => appendLog(line, cls);
</script>
</body>
</html>
"""


def _build_service_cards() -> str:
    cards = []
    for svc in SERVICES:
        cards.append(
            f"""
      <div class="card" id="card-{svc['name']}">
        <div class="card-head">
          <span class="name">{svc['name']}</span>
          <span class="state stopped" data-name="{svc['name']}">● 已停止</span>
        </div>
        <div class="card-head">
          <span class="swatch" style="background:#475569"></span>
          <span class="meta">端口 {svc['port']}</span>
        </div>
        <div class="desc">{svc['label']}</div>
      </div>"""
        )
    return "".join(cards)


def _build_card_index() -> str:
    return (
        "{"
        + ", ".join(
            f"'{svc['name']}': {{el: document.getElementById('card-{svc['name']}'),"
            f" state: document.querySelector('.state[data-name=\\\"{svc['name']}\\\"]'),"
            f" swatch: document.querySelectorAll('.swatch')[{i}],"
            f" port: {svc['port']}}}"
            for i, svc in enumerate(SERVICES)
        )
        + "}"
    )


def render_gui_html() -> str:
    return (
        GUI_HTML
        .replace("__APP_NAME__", APP_NAME)
        .replace("__APP_VERSION__", APP_VERSION)
        .replace("__CONSOLE_URL__", CONSOLE_URL)
        .replace("__STATUS_HOST__", STATUS_HOST)
        .replace("__STATUS_PORT__", str(STATUS_PORT))
        .replace("__SERVICE_CARDS__", _build_service_cards())
        .replace("__CARD_INDEX__", _build_card_index())
    )


# ---------------------------------------------------------------------------
# Local static-file HTTP server hosting the HTML on 127.0.0.1:8766
# (pywebview needs an http URL, not a data: URL, on Windows)
# ---------------------------------------------------------------------------
class _GuiHandler(BaseHTTPRequestHandler):
    gui_html: str = "<h1>loading...</h1>"

    def log_message(self, *_args) -> None:
        pass

    def do_GET(self) -> None:  # noqa: N802
        if self.path in ("/", "/index.html"):
            body = self.gui_html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()


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
        self._gui_server: Optional[ThreadingHTTPServer] = None
        self._gui_thread: Optional[threading.Thread] = None
        self._log_lock = threading.Lock()
        self._log_q: "queue.Queue[tuple[str,str]]" = queue.Queue()
        self._window = None
        self._tray_icon = None
        LOG_DIR.mkdir(parents=True, exist_ok=True)

    # ---------------- logging ----------------
    def _log(self, msg: str) -> None:
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        print(line, flush=True)
        with self._log_lock:
            try:
                with LOG_PATH.open("a", encoding="utf-8") as f:
                    f.write(f"[{datetime.now().isoformat(timespec='seconds')}] {msg}\n")
            except Exception:
                pass
        self._log_q.put(("sys", msg))

    # ---------------- lifecycle ----------------
    def start_all(self) -> str:
        any_alive = any(st.proc and st.proc.poll() is None for st in self.states.values())
        if any_alive:
            self._log("服务已在运行。")
            return "already-running"

        enabled = [s for s in SERVICES if s.get("enabled", True)]
        disabled = [s for s in SERVICES if not s.get("enabled", True)]
        if not enabled:
            self._log("没有已启用的服务，跳过启动。")
            return "no-enabled-services"
        if disabled:
            names = ", ".join(s["name"] for s in disabled)
            self._log(
                f"正在启动 {len(enabled)} 个服务（{names} 已禁用），本地 uvicorn…"
            )
        else:
            self._log("正在启动三个服务（本地 uvicorn）…")
        for svc in enabled:
            self._spawn(svc["name"])
        if self._supervisor is None or not self._supervisor.is_alive():
            self._supervisor = threading.Thread(target=self._supervise, daemon=True)
            self._supervisor.start()
        return "started"

    def _spawn(self, name: str) -> None:
        st = self.states[name]
        if st.proc and st.proc.poll() is None:
            return
        cfg = st.cfg
        if not cfg.get("enabled", True):
            st.last_error = "disabled in console config"
            self._log(f"[{name}] 已禁用（配置中 enabled=false），不启动。")
            return
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
                    "-m", "uvicorn",
                    cfg["module"],
                    "--host", "127.0.0.1",
                    "--port", str(cfg["port"]),
                    "--log-level", "info",
                ],
                cwd=str(cfg["cwd"]),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
            )
        except FileNotFoundError as e:
            st.last_error = f"启动失败: {e}"
            self._log(f"[{name}] 启动失败: {e}")
            return
        st.proc = proc
        st.started_at = time.time()
        st.last_error = ""
        self._log(f"[{name}] 已启动，pid={proc.pid}，端口 {cfg['port']}")
        threading.Thread(
            target=self._reader_thread, args=(name, proc.stdout), daemon=True
        ).start()

    def _reader_thread(self, name: str, stream) -> None:
        for raw in iter(stream.readline, b""):
            try:
                line = raw.decode("utf-8", errors="replace").rstrip()
            except Exception:
                continue
            if line:
                self._log(f"[{name}] {line}")
                cls = "s-" + name.split("-")[0] if "-" in name else ""
                self._log_q.put((cls, line))
        stream.close()

    def _supervise(self) -> None:
        all_ready_logged = False
        while not self._stopping:
            for svc in SERVICES:
                st = self.states[svc["name"]]
                if not cfg_enabled(svc):
                    # Disabled services don't pollute all_healthy and aren't health-checked.
                    continue
                if not st.proc:
                    st.healthy = False
                    continue
                if st.proc.poll() is not None:
                    st.healthy = False
                    st.last_error = f"进程退出，码 {st.proc.returncode}"
                    continue
                url = f"http://127.0.0.1:{svc['port']}/healthz"
                ok = _http_get(url, timeout=0.6)
                if ok and not st.healthy:
                    self._log(f"[{svc['name']}] 健康检查通过：{url}")
                st.healthy = ok
            enabled_svcs = [s for s in SERVICES if s.get("enabled", True)]
            ready = all(self.states[s["name"]].healthy for s in enabled_svcs) and bool(enabled_svcs)
            if ready and not all_ready_logged:
                all_ready_logged = True
                self._log("所有已启用服务全部健康。")
                self._log(f"控制台地址：{CONSOLE_URL}")
            elif not ready:
                all_ready_logged = False
            time.sleep(1.5)

    def stop_all(self) -> str:
        self._log("正在停止服务…")
        self._stopping = True
        for st in self.states.values():
            _terminate(st.proc)
            st.proc = None
            st.healthy = False
        self._stopping = False
        self._log("所有服务已停止。")
        return "stopped"

    # ---------------- status ----------------
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
            enabled = svc.get("enabled", True)
            running = bool(st.proc and st.proc.poll() is None)
            if not enabled:
                # Disabled services are explicitly *not* counted toward all_healthy
                # and are not flagged as errors.  They show up in the status with
                # a distinct "disabled" state so the UI can render them greyed out.
                out["services"][svc["name"]] = {
                    "port": svc["port"],
                    "enabled": False,
                    "running": False,
                    "healthy": False,
                    "state": "disabled",
                    "last_error": "",
                }
                continue
            if running:
                any_proc = True
            if not st.healthy:
                all_healthy = False
            out["services"][svc["name"]] = {
                "port": svc["port"],
                "enabled": True,
                "running": running,
                "healthy": st.healthy,
                "state": "running" if running else "stopped",
                "last_error": st.last_error,
            }
        out["all_healthy"] = all_healthy and any_proc
        return out

    # ---------------- servers ----------------
    def start_status_server(self) -> None:
        launcher = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args) -> None:
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
            self._log(f"状态服务绑定失败：{e}")
            return
        self._status_thread = threading.Thread(
            target=self._status_server.serve_forever, daemon=True
        )
        self._status_thread.start()
        self._log(f"状态端点：http://{STATUS_HOST}:{STATUS_PORT}/status")

    def start_gui_server(self) -> None:
        _GuiHandler.gui_html = render_gui_html()
        try:
            self._gui_server = ThreadingHTTPServer(
                ("127.0.0.1", LOCAL_GUI_PORT), _GuiHandler
            )
        except OSError as e:
            self._log(f"GUI 服务绑定失败：{e}")
            return
        self._gui_thread = threading.Thread(
            target=self._gui_server.serve_forever, daemon=True
        )
        self._gui_thread.start()
        self._log(f"GUI：http://127.0.0.1:{LOCAL_GUI_PORT}/")

    # ---------------- tray / browser actions ----------------
    def open_console(self) -> None:
        if _http_get(CONSOLE_URL, timeout=1.0):
            webbrowser.open(CONSOLE_URL)
            self._log(f"已在默认浏览器中打开 {CONSOLE_URL}。")
        else:
            self._log(f"控制台尚未就绪：{CONSOLE_URL}")

    def open_status(self) -> None:
        webbrowser.open(f"http://{STATUS_HOST}:{STATUS_PORT}/status")
        self._log("已打开状态 JSON。")

    def open_logs(self) -> None:
        try:
            if os.name == "nt":
                os.startfile(str(LOG_PATH))  # type: ignore[attr-defined]
            else:
                webbrowser.open(f"file://{LOG_PATH}")
        except Exception as e:
            self._log(f"打开日志失败：{e}")

    def quit_app(self) -> None:
        self.stop_all()
        for srv in (self._status_server, self._gui_server):
            try:
                if srv:
                    srv.shutdown()
            except Exception:
                pass
        try:
            if self._tray_icon:
                self._tray_icon.stop()
        except Exception:
            pass
        try:
            if self._window:
                self._window.destroy()
        except Exception:
            pass
        sys.exit(0)


# ---------------------------------------------------------------------------
# API exposed to the pywebview JS
# ---------------------------------------------------------------------------
class _Api:
    def __init__(self, launcher: Launcher) -> None:
        self.launcher = launcher

    def start_all(self) -> str:
        return self.launcher.start_all()

    def stop_all(self) -> str:
        return self.launcher.stop_all()

    def open_console(self) -> None:
        return self.launcher.open_console()

    def open_status(self) -> None:
        return self.launcher.open_status()

    def open_logs(self) -> None:
        return self.launcher.open_logs()

    def quit_app(self) -> None:
        return self.launcher.quit_app()

    def get_state(self) -> str:
        return json.dumps(self.launcher.snapshot())


# ---------------------------------------------------------------------------
# pywebview polling loop (drives live updates into the HTML)
# ---------------------------------------------------------------------------
def _poll_gui(window, launcher: Launcher, api: _Api) -> None:
    try:
        state = json.dumps(launcher.snapshot())
        window.evaluate_js(f"updateState({json.dumps(state)})")
    except Exception:
        pass
    try:
        while True:
            tag, line = launcher._log_q.get_nowait()
            window.evaluate_js(
                f"appendLog({json.dumps(line + chr(10))}, {json.dumps(tag)})"
            )
    except queue.Empty:
        pass
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> int:
    launcher = Launcher()
    launcher._log(f"{APP_NAME} v{APP_VERSION} 启动中…")
    launcher.start_status_server()
    launcher.start_gui_server()

    import webview

    api = _Api(launcher)
    gui_url = f"http://127.0.0.1:{LOCAL_GUI_PORT}/"

    window = webview.create_window(
        APP_NAME,
        url=gui_url,
        width=900,
        height=620,
        resizable=True,
        text_select=True,
        js_api=api,
        confirm_close=True,
    )
    launcher._window = window

    def poll_loop() -> None:
        while True:
            try:
                _poll_gui(window, launcher, api)
            except Exception:
                pass
            time.sleep(0.5)

    threading.Thread(target=poll_loop, daemon=True).start()

    # Auto-start the enabled services once the launcher has finished wiring up its
    # UI / supervisor.  Without this, the user has to click "启动服务" in the
    # WebView2 window, which is friction for a single-purpose console.
    try:
        launcher.start_all()
    except Exception as e:
        launcher._log(f"自动启动服务失败：{e}")

    launcher._log(
        f"{APP_NAME} 已就绪，正在启动系统托盘图标和主窗口…"
    )
    webview.start(gui=None, debug=False)
    launcher._log("主窗口已关闭，正在清理…")
    launcher.quit_app()
    return 0


if __name__ == "__main__":
    sys.exit(main())
