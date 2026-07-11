"""Rate-limit probe: step-up cadence publishing to empirically map XHS throttle boundaries."""
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

REPO_ROOT = Path(__file__).parent.parent
ACCOUNT_ID = "acc_676072139"
TASK_NAME = "莫大博士招生 · 限流探测"
OUT_DIR = REPO_ROOT / "logs"
FINDINGS_PATH = REPO_ROOT / "docs" / "rate_limit_probe_findings.md"

CIRCUIT_BREAK_SIGNALS = {
    "429", "flow_limit", "服务繁忙", "黑名单", "发布太频繁",
    "rate limit", "throttl", "banned", "封号",
}


def ts_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")


def epoch_ms() -> float:
    return time.time() * 1000


def check_limit_signal(error: str) -> Optional[str]:
    if error:
        e = error.lower()
        for sig in CIRCUIT_BREAK_SIGNALS:
            if sig.lower() in e:
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
        pass


def print_status(rung: int, interval: int, attempt: int, outcome: str, latency: float) -> None:
    bar = "\u2588" * min(attempt, 10)
    print(f"  [R{rung} {interval:2d}m] attempt {attempt}: {outcome:<14s} {bar}  {latency:,.0f} ms", flush=True)


sys.path.insert(0, str(REPO_ROOT / "xiaohongshu-saas"))

from app.channels import registry as channel_registry
from app.core.config import settings
from app.core.types import PublishResult
from app.content_factory import factory
from app.db.session import init_db, session_scope
from app.models import Account, Task
from sqlalchemy import select


async def load_account_and_task(session) -> tuple:
    account = await session.get(Account, ACCOUNT_ID)
    if not account:
        raise RuntimeError(f"Account {ACCOUNT_ID} not found - run scripts/seed_mgu_phd.py first")
    task_row = await session.execute(
        select(Task).where(Task.name == TASK_NAME)
    )
    task_row = task_row.scalar_one_or_none()
    if not task_row:
        raise RuntimeError(f'Task "{TASK_NAME}" not found - run scripts/seed_mgu_phd.py first')
    return account, task_row


async def probe_one(
    cookie_path: str,
    template_key: str,
    csv_path: Path,
    rung: int,
    interval_min: int,
    attempt: int,
) -> tuple[str, Optional[str], float]:
    t0 = epoch_ms()
    outcome = "success"
    throttle_signal: Optional[str] = None
    publish_id = ""

    try:
        class _Acct:
            def __init__(self, cp: str, aid: str):
                self.id = aid
                self.cookie_path = cp
                self.proxy: Optional[str] = None

        adapter = channel_registry.get("xiaohongshu")
        template = factory.load_template(template_key)
        content = factory.render(template)
        result: PublishResult = await adapter.publish(_Acct(cookie_path, ACCOUNT_ID), content)

        if result.success:
            outcome = "success"
            publish_id = str(result.external_id or "")
        else:
            outcome = "failed"
            sig = check_limit_signal(result.error or "")
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
        "ts": ts_now(), "rung": rung, "interval_min": interval_min,
        "attempt": attempt, "outcome": outcome,
        "error": outcome if "failed" in outcome or "exception" in outcome else "",
        "throttle_signal": throttle_signal or "",
        "publish_id": publish_id,
        "latency_ms": round(latency),
    })
    return outcome, throttle_signal, latency


async def run_probe(rungs: list[int], headed: bool = False) -> dict:
    settings.app_env = "dev"
    await init_db()
    channel_registry.bootstrap()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    FINDINGS_PATH.parent.mkdir(parents=True, exist_ok=True)

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = OUT_DIR / f"rate_probe_{ts}.csv"
    findings = {
        "rungs": [], "stopped_early": False,
        "stop_reason": "", "total_attempts": 0, "total_success": 0,
    }

    print(f"=== Rate-limit probe {ts_now()} ===")
    print(f"  CSV: {csv_path}")
    print(f"  Rungs: {rungs}  headed={headed}")
    print()

    async with session_scope() as session:
        account, task = await load_account_and_task(session)
        cookie_path = account.cookie_path or ""
        account_stage = account.stage

    if not cookie_path or not Path(cookie_path).exists():
        print(f"FATAL: cookie file missing: {cookie_path}")
        print(f"  Run: python scripts/harvest_xhs_cookie.py --account-id {ACCOUNT_ID}")
        return findings

    if account_stage == "banned":
        findings["stopped_early"] = True
        findings["stop_reason"] = "account banned"
        print(f"FATAL: account is banned (stage={account_stage})")
        return findings

    for rung_idx, interval_min in enumerate(rungs):
        rung_num = rung_idx + 1
        print(f"\n--- RUNG {rung_num}/{len(rungs)}: {interval_min} min ---")
        rung_ok = rung_fail = rung_throttle = 0
        consec_fail = 0

        for attempt in range(1, 3):
            outcome, throttle_sig, latency = await probe_one(
                cookie_path, task.template_key, csv_path,
                rung_num, interval_min, attempt,
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

            if consec_fail >= 3:
                msg = f"circuit break: {consec_fail} consecutive failures"
                print(f"  STOP: {msg}")
                findings["stopped_early"] = True
                findings["stop_reason"] = msg
                break

            if attempt < 2:
                print(f"  waiting 5s between attempts...")
                await asyncio.sleep(5)

        findings["rungs"].append({
            "rung": rung_num, "interval_min": interval_min,
            "ok": rung_ok, "failed": rung_fail, "throttled": rung_throttle,
        })

        if findings["stopped_early"]:
            break
        if rung_idx < len(rungs) - 1:
            print(f"  sleeping {interval_min} min until next rung...")
            await asyncio.sleep(interval_min * 60)

    print()
    print(f"PROBE COMPLETE {ts_now()}")
    print(f"  Total: {findings['total_attempts']}  OK: {findings['total_success']}")
    if findings["stopped_early"]:
        print(f"  Stopped: {findings['stop_reason']}")

    hdr = f"{'Rung':<6} {'Interval':<10} {'OK':<4} {'Fail':<5} {'Throttle':<9} {'Verdict'}"
    print(hdr)
    print("-" * len(hdr))
    for r in findings["rungs"]:
        v = "throttled" if r["throttled"] else ("ok" if r["ok"] == 2 else "mixed")
        print(f"  {r['rung']:<4} {r['interval_min']:<8}m {r['ok']:<4} {r['failed']:<5} {r['throttled']:<9} {v}")

    _write_findings(findings, csv_path)
    return findings


def _write_findings(findings: dict, csv_path: Path) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M UTC+8")
    total = findings["total_attempts"]
    ok = findings["total_success"]
    rungs_md = ""
    for r in findings["rungs"]:
        v = "throttled" if r["throttled"] else ("ok" if r["ok"] == 2 else "mixed")
        rungs_md += f"| {r['rung']} | {r['interval_min']}m | {r['ok']} | {r['failed']} | {r['throttled']} | {v} |\n"

    md = (
        f"# Rate-limit Probe Findings\n\n"
        f"**Date:** {ts}\n"
        f"**Account:** {ACCOUNT_ID} (卡匹迪恩)\n"
        f"**Template:** mgu_phd\n"
        f"**CSV:** `{csv_path}`\n\n"
        f"## Summary\n\n"
        f"- Total attempts: {total}\n"
        f"- Success: {ok}\n"
        f"- Stopped early: {findings['stopped_early']} - {findings['stop_reason']}\n\n"
        f"## Per-Rung Results\n\n"
        f"| Rung | Interval | OK | Failed | Throttled | Verdict |\n"
        f"|------|----------|----|--------|-----------|--------|\n"
        f"{rungs_md}"
        f"## Observations\n\n"
        f"_Manually fill in after reviewing the CSV and XHS creator dashboard screenshots._\n\n"
        f"## Recommendations\n\n"
        f"_Manually fill in after observing at which rung 限流 fires._\n\n"
        f"## Next Steps\n\n"
        f"1. Set `interval_minutes` in the Task row based on the last safe rung.\n"
        f"2. If no 限流 observed, push the cadence higher.\n"
        f"3. Monitor the account stage in the DB after 24h - if it transitions to `cooling` or `banned`, pause all publishing.\n"
    )
    FINDINGS_PATH.write_text(md, encoding="utf-8")
    print(f"  Findings written to: {FINDINGS_PATH}")


def main() -> int:
    p = argparse.ArgumentParser(description="XHS rate-limit probe")
    p.add_argument("--rungs", default="30,20,10,5,2",
        help="comma-separated step-up intervals in minutes")
    p.add_argument("--headed", action="store_true",
        help="run Chromium in non-headless mode so you can watch the posts")
    args = p.parse_args()

    rungs = [int(x) for x in args.rungs.split(",") if x.strip()]
    if not rungs:
        print("ERROR: --rungs must be non-empty")
        return 1

    try:
        asyncio.run(run_probe(rungs, headed=args.headed))
        return 0
    except KeyboardInterrupt:
        print("\nProbe cancelled by user.")
        return 130


if __name__ == "__main__":
    sys.exit(main())
