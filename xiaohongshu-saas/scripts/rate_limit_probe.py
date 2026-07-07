"""Rate-limit probe: step-up cadence publishing to empirically map XHS throttle boundaries.

Usage:
    python scripts/rate_limit_probe.py                       # defaults: 30,20,10,5,2 min rungs
    python scripts/rate_limit_probe.py --rungs 15,5,2       # custom rungs
    python scripts/rate_limit_probe.py --headed             # non-headless Chromium

Output:
    logs/rate_probe_<ts>.csv  — per-attempt CSV log
    docs/rate_limit_probe_findings.md  — findings summary
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ── bootstrap so app imports work ────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.channels import registry as channel_registry
from app.core.config import settings
from app.core.logging import logger
from app.core.types import ContentItem, PublishResult
from app.content_factory import factory
from app.db.session import init_db, session_scope
from app.models import Account, Publish, PublishStatus, Task
from sqlalchemy import select

ACCOUNT_ID = "acc_676072139"
TASK_NAME  = "莫大博士招生 · 限流探测"
FINDINGS_PATH = Path("docs/rate_limit_probe_findings.md")
OUT_DIR = Path("logs")
OUT_DIR.mkdir(parents=True, exist_ok=True)
FINDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)

PROBE_TOPICS = ["莫斯科国立大学", "博士招生", "俄罗斯留学", "海外博士申请"]
PROBE_TITLE_PREFIX = "莫大博士招生"

CIRCUIT_BREAK_SIGNALS = {
    "429", "flow_limit", "服务繁忙", "黑名单",
    "发布太频繁", "rate limit", "throttl", "banned", "封号",
}

# ── helpers ────────────────────────────────────────────────────────────────────

def ts_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def epoch_ms() -> float:
    return time.time() * 1000


def load_account_and_task(session) -> tuple[Account, Task]:
    account = session.get(Account, ACCOUNT_ID)
    if not account:
        raise RuntimeError(f"Account {ACCOUNT_ID} not found — run scripts/seed_mgu_phd.py first")
    task_row = session.execute(
        select(Task).where(Task.name == TASK_NAME)
    ).scalar_one_or_none()
    if not task_row:
        raise RuntimeError(f'Task "{TASK_NAME}" not found — run scripts/seed_mgu_phd.py first')
    return account, task_row


def check_limit_signal(result: PublishResult) -> Optional[str]:
    if result.error:
        err = result.error.lower()
        for sig in CIRCUIT_BREAK_SIGNALS:
            if sig.lower() in err:
                return sig
    return None


def write_csv_row(csv_path: Path, row: dict) -> None:
    write_header = not csv_path.exists()
    with open(csv_path, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=[
            "ts", "rung", "interval_min", "attempt", "outcome",
            "error", "throttle_signal", "publish_id", "latency_ms",
        ])
        if write_header:
            w.writeheader()
        w.writerow(row)


async def emit_sse_event(event_type: str, data: dict) -> None:
    """Append an event to the SSE queue (consumed by /api/events/recent)."""
    # The simplest SSE integration is to POST to the internal event bus.
    # If the bus isn't running we just log and continue.
    try:
        import urllib.request
        body = json.dumps({"type": event_type, "data": data}).encode("utf-8")
        req = urllib.request.Request(
            "http://127.0.0.1:8080/api/events/probe",
            data=body, method="POST",
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=2)
    except Exception:
        pass  # non-critical


def print_status(rung: int, interval: int, attempt: int, outcome: str, latency: float) -> None:
    bar = "█" * min(attempt, 10)
    print(f"  [R{rung} {interval:2d}m] attempt {attempt}: {outcome:<12s}  {bar}  {latency:,.0f} ms")


# ── core probe logic ──────────────────────────────────────────────────────────

async def probe_one(
    account: Account,
    template_key: str,
    csv_path: Path,
    rung: int,
    interval_min: int,
    attempt: int,
) -> tuple[str, Optional[str], int, float]:
    """Publish one note. Returns (outcome, throttle_signal, publish_id, latency_ms)."""
    t0 = epoch_ms()
    outcome = "success"
    throttle_signal: Optional[str] = None
    publish_id = ""

    try:
        adapter = registry.get("xiaohongshu")
        template = factory.load_template(template_key)
        content = factory.render(template)

        result: PublishResult = await adapter.publish(account, content)

        if result.success:
            outcome = "success"
            publish_id = str(result.external_id or "")
        else:
            outcome = "failed"
            sig = check_limit_signal(result)
            if sig:
                throttle_signal = sig
                outcome = f"throttled({sig})"
            print(f"    FAILED: {result.error}")

    except Exception as exc:
        outcome = "exception"
        print(f"    EXCEPTION: {exc}")
        traceback.print_exc()

    latency = epoch_ms() - t0
    write_csv_row(csv_path, {
        "ts": ts_now(),
        "rung": rung,
        "interval_min": interval_min,
        "attempt": attempt,
        "outcome": outcome,
        "error": outcome if "failed" in outcome or "exception" in outcome else "",
        "throttle_signal": throttle_signal or "",
        "publish_id": publish_id,
        "latency_ms": round(latency),
    })
    return outcome, throttle_signal, latency


async def run_probe(rungs: list[int], headed: bool = False) -> dict:
    settings.app_env = "dev"
    if headed:
        settings.app_env = "dev"  # headed Chromium is controlled by adapter

    await init_db()
    channel_registry.bootstrap()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = OUT_DIR / f"rate_probe_{ts}.csv"
    findings: dict = {
        "rungs": [],
        "stopped_early": False,
        "stop_reason": "",
        "total_attempts": 0,
        "total_success": 0,
    }

    print(f"=== Rate-limit probe started at {ts_now()} ===")
    print(f"    CSV log: {csv_path}")
    print(f"    Rungs:   {rungs}")
    print(f"    Headless: {not headed}")
    print()

    async with session_scope() as session:
        account, task = load_account_and_task(session)

        if not account.cookie_path or not Path(account.cookie_path).exists():
            print(f"FATAL: cookie file missing: {account.cookie_path}")
            print(f"  Run: python -m scripts.harvest_xhs_cookie --account-id {ACCOUNT_ID}")
            return findings

        if account.stage == "banned":
            print(f"FATAL: account is banned (stage={account.stage})")
            findings["stopped_early"] = True
            findings["stop_reason"] = "account banned"
            return findings

    prev_throttle: Optional[str] = None

    for rung_idx, interval_min in enumerate(rungs):
        rung_num = rung_idx + 1
        print(f"\n{'='*60}")
        print(f"RUNG {rung_num}/rungs={rungs}: interval={interval_min} min")
        print(f"{'='*60}")

        rung_ok, rung_fail, rung_throttle = 0, 0, 0
        consec_fail = 0

        for attempt in range(1, 3):  # 2 attempts per rung
            outcome, throttle_sig, latency = await probe_one(
                account, task.template_key, csv_path, rung_num, interval_min, attempt
            )
            findings["total_attempts"] += 1
            print_status(rung_num, interval_min, attempt, outcome, latency)

            await emit_sse_event("probe_attempt", {
                "rung": rung_num, "interval": interval_min,
                "attempt": attempt, "outcome": outcome, "latency_ms": latency,
            })

            if "success" in outcome:
                findings["total_success"] += 1
                rung_ok += 1
                consec_fail = 0
            else:
                rung_fail += 1
                consec_fail += 1
                if throttle_sig:
                    rung_throttle += 1
                    prev_throttle = throttle_sig

            # Circuit breaker: 3 consecutive failures
            if consec_fail >= 3:
                msg = f"circuit break: {consec_fail} consecutive failures"
                print(f"\n  STOP: {msg}")
                findings["stopped_early"] = True
                findings["stop_reason"] = msg
                break

            # Wait between attempts within a rung
            if attempt < 2:
                wait_s = 5
                print(f"  waiting {wait_s}s between attempts...")
                await asyncio.sleep(wait_s)

        findings["rungs"].append({
            "rung": rung_num,
            "interval_min": interval_min,
            "ok": rung_ok,
            "failed": rung_fail,
            "throttled": rung_throttle,
        })

        if findings["stopped_early"]:
            break

        # Wait between rungs (the interval itself)
        if rung_idx < len(rungs) - 1:
            next_interval = rungs[rung_idx + 1]
            print(f"\n  rung done. sleeping {interval_min} min until next rung ({next_interval} min)...")
            await asyncio.sleep(interval_min * 60)

    # ── print findings table ─────────────────────────────────────────────────
    print()
    print(f"{'='*60}")
    print(f"PROBE COMPLETE at {ts_now()}")
    print(f"Total attempts: {findings['total_attempts']}  success: {findings['total_success']}")
    if findings['stopped_early']:
        print(f"Stopped early: {findings['stop_reason']}")
    print()
    print(f"{'Rung':<6} {'Interval':<10} {'OK':<4} {'Fail':<5} {'Throttle':<9} {'Verdict'}")
    print("-" * 55)
    for r in findings["rungs"]:
        verdict = "throttled" if r["throttled"] else ("ok" if r["ok"] == 2 else "mixed")
        print(f"  {r['rung']:<4} {r['interval_min']:<8}m {r['ok']:<4} {r['failed']:<5} {r['throttled']:<9} {verdict}")

    # ── write findings.md ────────────────────────────────────────────────────
    _write_findings(findings, csv_path)
    return findings


def _write_findings(findings: dict, csv_path: Path) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M UTC+8")
    total = findings["total_attempts"]
    ok = findings["total_success"]
    rungs_md = ""
    for r in findings["rungs"]:
        verdict = "throttled" if r["throttled"] else ("ok" if r["ok"] == 2 else "mixed")
        rungs_md += f"| {r['rung']} | {r['interval_min']}m | {r['ok']} | {r['failed']} | {r['throttled']} | {verdict} |\n"

    md = f"""# Rate-limit Probe Findings

**Date:** {ts}  
**Account:** {ACCOUNT_ID}  
**Template:** mgu_phd  
**CSV:** `{csv_path}`

## Summary

- Total attempts: {total}
- Success: {ok}
- Stopped early: {findings['stopped_early']} — {findings['stop_reason']}

## Per-Rung Results

| Rung | Interval | OK | Failed | Throttled | Verdict |
|------|----------|----|--------|-----------|---------|
{rungs_md}## Observations

_Manually fill in after reviewing the CSV and XHS creator dashboard screenshots._

## Recommendations

_Manually fill in after observing at which rung 限流 fires._

## Next Steps

1. Set `interval_minutes` in the Task row based on the last safe rung.
2. If no 限流 observed at rung {len(findings['rungs'])+1 if not findings['stopped_early'] else findings['rungs'][-1]['rung']}, push the cadence higher.
3. Monitor the account stage in the DB after 24h — if it transitions to `cooling` or `banned`, pause all publishing.
"""
    FINDINGS_PATH.write_text(md, encoding="utf-8")
    print(f"  Findings written to: {FINDINGS_PATH}")


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> int:
    p = argparse.ArgumentParser(description="XHS rate-limit probe")
    p.add_argument(
        "--rungs", default="30,20,10,5,2",
        help="comma-separated step-up intervals in minutes (default: 30,20,10,5,2)",
    )
    p.add_argument(
        "--headed", action="store_true",
        help="run Chromium in non-headless mode so you can watch the posts",
    )
    args = p.parse_args()

    rungs = [int(x) for x in args.rungs.split(",") if x.strip()]
    if not rungs:
        print("ERROR: --rungs must be non-empty")
        return 1

    try:
        findings = asyncio.run(run_probe(rungs, headed=args.headed))
        return 0 if not findings.get("stopped_early") else 0
    except KeyboardInterrupt:
        print("\nProbe cancelled by user.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
