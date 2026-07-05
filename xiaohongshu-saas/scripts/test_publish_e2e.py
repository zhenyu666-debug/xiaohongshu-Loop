"""End-to-end test driver for xiaohongshu publishing.

Sequence
--------
1. Make sure all three services are up (use ``scripts/console_gui.py`` if not).
2. Make sure an ``Account`` row exists in SQLite with risk-overrides applied
   (stage=normal, warmup_until=None) and ``cookie_path`` pointing to a path the
   harvest script will write to.
3. Make sure a ``Task`` row exists bound to that account using template ``demo``.
4. Drive the cookie harvest (headed Chromium, user scans QR) and wait for
   ``data/cookies/<account_id>.json`` to appear AND the heartbeat to return alive.
5. POST ``/api/tasks/{task_id}/run`` -> runner -> XiaohongshuAdapter.publish().
6. Poll SQLite until a ``publishes`` row appears with ``status='success'``.
7. Listen on SSE (best-effort; the publish_event() emitter is unwired in some
   versions, so SSE arrival is informational, not a hard assertion).
8. Print PASS/FAIL summary.

Usage
-----
    python scripts/test_publish_e2e.py
    python scripts/test_publish_e2e.py --skip-cookie   # reuse existing cookie
    python scripts/test_publish_e2e.py --account-id acc_e2e
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
XHS_DIR = REPO_ROOT / "xiaohongshu-saas"
COOKIE_DIR = XHS_DIR / "data" / "cookies"
DB_PATH = XHS_DIR / "data" / "xhs_saas.db"

BASE_URL = "http://127.0.0.1:8080"
DEFAULT_ACCOUNT_ID = "acc_e2e"
DEFAULT_TASK_NAME = "e2e_pub_task"

_LAUNCHER = None  # keep reference for ad-hoc inspection


# ---------------------------------------------------------------------------
# Light helpers
# ---------------------------------------------------------------------------
def _http_json(method, url, payload=None, timeout=6.0):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(
        url, data=data, method=method,
        headers={"Content-Type": "application/json"} if data else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            try:
                return resp.status, json.loads(raw)
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", errors="replace")
    except Exception as e:
        return 0, "{}: {}".format(type(e).__name__, e)


def health_check():
    for port in (8080, 8090, 8091):
        try:
            urllib.request.urlopen("http://127.0.0.1:{}/healthz".format(port), timeout=1)
        except Exception as e:
            print("  x port {} down: {}".format(port, type(e).__name__))
            return False
    return True


def ensure_launcher_up():
    """Start the three services via console_gui.Launcher if not already running."""
    if health_check():
        print("[launcher] services already healthy; reusing")
        return
    sys.path.insert(0, str(REPO_ROOT / "scripts"))
    import console_gui  # noqa: E402
    launcher = console_gui.Launcher()
    launcher.start_status_server()
    launcher.start_gui_server()
    result = launcher.start_all()
    print("[launcher] {}".format(result))
    global _LAUNCHER
    _LAUNCHER = launcher


def wait_for_healthz(max_wait=25.0):
    t0 = time.monotonic()
    while time.monotonic() - t0 < max_wait:
        if health_check():
            return True
        time.sleep(0.6)
    return False


# ---------------------------------------------------------------------------
# Account + Task setup
# ---------------------------------------------------------------------------
def db_conn():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def upsert_account(account_id, nickname, cookie_path):
    """REST POST /api/accounts, then patch row via SQL to bypass warmup/cooldowns."""
    status, payload = _http_json("GET", "{}/api/accounts".format(BASE_URL))
    rows = payload if isinstance(payload, list) else []
    existing = next((a for a in rows if a.get("id") == account_id), None)

    if not existing:
        status, payload = _http_json("POST", "{}/api/accounts".format(BASE_URL), {
            "id": account_id,
            "channel": "xiaohongshu",
            "nickname": nickname,
            "enabled": True,
        })
        if status not in (200, 201):
            raise RuntimeError("create account failed: {} {}".format(status, payload))
    else:
        print("  - account {} already exists, reusing".format(account_id))

    cookie_path.parent.mkdir(parents=True, exist_ok=True)
    with db_conn() as conn:
        conn.execute(
            """UPDATE accounts SET stage='normal', warmup_until=NULL,
               fail_streak=0, last_fail_at=NULL,
               cookie_path=?, enabled=1 WHERE id=?""",
            (str(cookie_path), account_id),
        )
        conn.commit()
    return {"id": account_id, "cookie_path": str(cookie_path)}


def ensure_task(account_id, template_key="demo"):
    """Return task_id; reuse if a task already binds account_id + template_key."""
    status, payload = _http_json("GET", "{}/api/tasks".format(BASE_URL))
    tasks = payload if isinstance(payload, list) else []
    for t in tasks:
        if (t.get("account_ids") == [account_id]
                and t.get("template_key") == template_key
                and t.get("channel") == "xiaohongshu"):
            print("  - reusing task id={} name={!r}".format(t["id"], t["name"]))
            return int(t["id"])

    status, payload = _http_json("POST", "{}/api/tasks".format(BASE_URL), {
        "name": DEFAULT_TASK_NAME,
        "channel": "xiaohongshu",
        "account_ids": [account_id],
        "template_key": template_key,
        "kind": "loop",
        "status": "draft",
        "interval_minutes": 60,
        "jitter_minutes": 5,
        "window_start": "00:00",
        "window_end": "23:59",
        "use_ai": False,
    })
    if status not in (200, 201):
        raise RuntimeError("create task failed: {} {}".format(status, payload))
    new_id = payload["id"] if isinstance(payload, dict) else None
    if new_id is None:
        raise RuntimeError("create task: missing id in response")
    print("  - created task id={}".format(new_id))
    return int(new_id)


# ---------------------------------------------------------------------------
# Cookie harvest
# ---------------------------------------------------------------------------
def harvest_cookie(account_id, timeout_s=180):
    """Run scripts.harvest_xhs_cookie with APP_ENV=dev so Chromium is headed."""
    cookie_file = COOKIE_DIR / "{}.json".format(account_id)
    if cookie_file.exists() and cookie_file.stat().st_size > 200:
        print("[cookie] existing file present ({} bytes); reusing".format(cookie_file.stat().st_size))
        return True

    cmd = [sys.executable, str(XHS_DIR / "scripts" / "harvest_xhs_cookie.py"),
           "--account-id", account_id]
    print("[cookie] launching headed Chromium for QR scan: {}".format(" ".join(cmd)))
    print(">>> 用户请在浏览器里扫码登录 creator.xiaohongshu.com <<<")

    env = os.environ.copy()
    env["APP_ENV"] = "dev"
    # harvest script imports `app.*`; ensure XHS_DIR is on PYTHONPATH
    existing_pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = str(XHS_DIR) + (os.pathsep + existing_pp if existing_pp else "")
    proc = subprocess.Popen(
        cmd, cwd=str(XHS_DIR), env=env,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        text=True, encoding="utf-8",
    )

    t0 = time.monotonic()
    try:
        while time.monotonic() - t0 < timeout_s:
            if cookie_file.exists() and cookie_file.stat().st_size > 200:
                elapsed = time.monotonic() - t0
                print("[cookie] saved {} bytes after {:.1f}s".format(cookie_file.stat().st_size, elapsed))
                return True
            if proc.poll() is not None and time.monotonic() - t0 > 5:
                out, _ = proc.communicate(timeout=2)
                print("[cookie] harvest exited early:")
                print(out[-400:] if out else "(no stdout)")
                return False
            time.sleep(1.0)
    finally:
        if proc.poll() is None:
            try:
                proc.terminate()
                proc.wait(timeout=3)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

    print("[cookie] timeout after {}s; cookie file not written".format(timeout_s))
    return False


def heartbeat_ok(account_id):
    status, body = _http_json("POST", "{}/api/accounts/{}/heartbeat".format(BASE_URL, account_id))
    if status != 200 or not isinstance(body, dict):
        print("[heartbeat] non-200: {} {}".format(status, body))
        return False
    cookies_valid = bool(body.get("cookies_valid"))
    print("[heartbeat] {}".format(body))
    return cookies_valid


# ---------------------------------------------------------------------------
# Trigger + assert
# ---------------------------------------------------------------------------
def trigger_run(task_id):
    status, body = _http_json("POST", "{}/api/tasks/{}/run".format(BASE_URL, task_id))
    print("[trigger] {} {}".format(status, body))
    if status != 200:
        raise RuntimeError("trigger run failed: {}".format(body))


def latest_publish_row(task_id):
    with db_conn() as conn:
        cur = conn.execute(
            "SELECT * FROM publishes WHERE task_id=? ORDER BY id DESC LIMIT 1",
            (task_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def wait_for_publish(task_id, timeout_s=120.0):
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout_s:
        row = latest_publish_row(task_id)
        if row and row.get("finished_at"):
            return row
        time.sleep(2.0)
    return None


def fetch_recent_events():
    events = []
    try:
        req = urllib.request.Request("{}/api/v1/events/recent?limit=50".format(BASE_URL))
        with urllib.request.urlopen(req, timeout=4) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            events = data.get("items", []) if isinstance(data, dict) else []
    except Exception as e:
        print("[sse] recent-list error: {}: {}".format(type(e).__name__, e))
    return events


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--account-id", default=DEFAULT_ACCOUNT_ID)
    parser.add_argument("--skip-launcher", action="store_true",
                        help="assume services are already running")
    parser.add_argument("--skip-cookie", action="store_true",
                        help="reuse existing cookie file if present")
    parser.add_argument("--no-run", action="store_true",
                        help="only set up account/task; do not trigger publish")
    parser.add_argument("--no-heartbeat", action="store_true",
                        help="skip /heartbeat check")
    args = parser.parse_args()

    print("[1/6] launcher status check ...")
    if not args.skip_launcher:
        ensure_launcher_up()
    if not wait_for_healthz():
        print("FAIL: services did not become healthy on 8080/8090/8091")
        return 1
    print("  ok - all three services healthy")

    print("[2/6] account row for {} ...".format(args.account_id))
    cookie_path = COOKIE_DIR / "{}.json".format(args.account_id)
    acc = upsert_account(args.account_id, "e2e_test", cookie_path)
    print("  ok - {}".format(acc))

    print("[3/6] task binding ...")
    task_id = ensure_task(args.account_id)
    print("  ok - task_id={}".format(task_id))

    if not args.skip_cookie:
        print("[4/6] cookie harvest (timeout 180s; user scans QR) ...")
        if not harvest_cookie(args.account_id, timeout_s=180):
            print("FAIL: cookie harvest failed/timeout")
            return 2

    if not args.no_heartbeat:
        print("[5/6] heartbeat ...")
        if not heartbeat_ok(args.account_id):
            print("WARN: heartbeat not alive; cookie may be invalid")
            return 3
        print("  ok - heartbeat alive")

    if args.no_run:
        print("--no-run set, stopping after setup")
        return 0

    print("[6/6] triggering POST /api/tasks/{}/run ...".format(task_id))
    trigger_run(task_id)

    print("  waiting for publishes row (up to 120s) ...")
    row = wait_for_publish(task_id, timeout_s=120)
    if not row:
        print("FAIL: no finished publish row after 120s")
        with db_conn() as conn:
            cur = conn.execute("SELECT id,status,error,started_at,finished_at FROM publishes "
                               "ORDER BY id DESC LIMIT 3")
            for r in cur.fetchall():
                print(" ", dict(r))
        return 4

    status_v = row.get("status")
    external_id = row.get("external_id")
    url_v = row.get("url")
    err = row.get("error")
    print("  row: status={} external_id={} url={} err={!r}".format(
        status_v, external_id, url_v, err))

    sse_events = fetch_recent_events()
    if sse_events:
        print("[sse] recent events ({}):".format(len(sse_events)))
        for e in sse_events[:5]:
            print("   - topic={} msg={}".format(e.get("topic"), e.get("message") or e))
    else:
        print("[sse] no recent events (publish_event emitter may be unwired in this build)")

    if status_v == "success" and external_id:
        print("PASS: post created on xiaohongshu")
        return 0
    if status_v == "failed":
        print("FAIL: publish failed: {}".format(err))
        return 5
    print("FAIL: unexpected status {!r}".format(status_v))
    return 6


if __name__ == "__main__":
    raise SystemExit(main())
