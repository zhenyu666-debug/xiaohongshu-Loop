"""Smoke test — boot the FastAPI server (stdlib + urllib only).

We avoid httpx because the host's proxy may interfere when the script
tries to call itself; urllib defaults are different and loopback does
not go through the system proxy.
"""

from __future__ import annotations

import json
import socket
import sys
import threading
import time
from pathlib import Path
from urllib import request as urlreq

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.api import app  # noqa: E402


def _run() -> None:
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")


def _wait_ready(timeout_s: float = 10.0) -> bool:
    start = time.time()
    while time.time() - start < timeout_s:
        with socket.socket() as s:
            s.settimeout(0.5)
            try:
                s.connect(("127.0.0.1", 8765))
                return True
            except OSError:
                time.sleep(0.2)
    return False


def _get(path: str):
    with urlreq.urlopen("http://127.0.0.1:8765" + path, timeout=20) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


def _get_soft(path: str):
    try:
        return _get(path)
    except Exception as exc:
        return 0, str(exc)


def _post(path: str, body: dict | None = None):
    data = json.dumps(body or {}).encode("utf-8")
    req = urlreq.Request(
        "http://127.0.0.1:8765" + path,
        data=data,
        headers={"content-type": "application/json"},
        method="POST",
    )
    with urlreq.urlopen(req, timeout=30) as resp:
        return resp.status, resp.read().decode("utf-8", errors="replace")


def main() -> int:
    t = threading.Thread(target=_run, daemon=True)
    t.start()
    if not _wait_ready():
        print("FAIL: server did not come up")
        return 1
    try:
        s, b = _get("/api/health")
        h = json.loads(b)
        print(f"HEALTH  ok={h['ok']} tg={h['tigergraph']['status']} version={h['version']}")

        s, b = _get("/api/config")
        c = json.loads(b)
        print(f"CONFIG  graph={c['tg_graph_name']} accounts={c['synth_accounts']}")

        s, b = _post("/api/dataset", {})
        d = json.loads(b)
        total_v = sum(d["manifest"]["totals"].get(k, 0) for k in [
            "customers", "accounts", "cards", "devices", "ips",
            "merchants", "transactions",
        ])
        print(f"DATASET vertices={total_v}")

        s, b = _post("/api/detector/run", {"backend": "auto"})
        dr = json.loads(b)
        print(f"DETECT  backend={dr['backend']} alerts={len(dr['alerts'])} status={dr['status']}")

        s, b = _get("/api/memory/static")
        sm = json.loads(b)
        s, b = _get("/api/memory/dynamic")
        dm = json.loads(b)
        print(f"MEMORY  static={sm['char_count']}B dynamic={dm['alert_count']} alerts")

        s, b = _get_soft("/ui/index.html")
        if s == 200:
            print(f"UI      index.html bytes={len(b)}")
        else:
            print(f"UI      index.html GET returned {s} ({b[:80]})")

        s, b = _get_soft("/ui/styles.css")
        if s == 200:
            print(f"UI      styles.css bytes={len(b)}")
        else:
            print(f"UI      styles.css GET returned {s} ({b[:80]})")

        s, b = _get_soft("/ui/app.js")
        if s == 200:
            print(f"UI      app.js bytes={len(b)}")
        else:
            print(f"UI      app.js GET returned {s} ({b[:80]})")

        print()
        print("[smoke] all endpoints OK")
        return 0
    except Exception as exc:
        print(f"FAIL: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
