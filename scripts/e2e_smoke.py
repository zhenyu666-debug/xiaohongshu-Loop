# End-to-end smoke test for the three-service stack.
#
# Requires: requests
# Usage:
#   1. docker compose up -d  (or run services individually)
#   2. python scripts/e2e_smoke.py
#
# Exits 0 if all checks pass, 1 otherwise.

from __future__ import annotations

import json
import sys
import time

import requests

SERVICES = {
    "xhs-saas": "http://localhost:8080",
    "pbp-api": "http://localhost:8090",
    "lakehouse-api": "http://localhost:8091",
}


def check(label: str, url: str, expect_keys: list[str] | None = None) -> bool:
    print(f"-> {label}: GET {url}")
    try:
        r = requests.get(url, timeout=10)
    except requests.RequestException as e:
        print(f"   FAIL: {e!r}")
        return False
    if r.status_code != 200:
        print(f"   FAIL: status={r.status_code}")
        return False
    try:
        body = r.json()
    except json.JSONDecodeError:
        body = r.text
    if expect_keys:
        missing = [k for k in expect_keys if not isinstance(body, dict) or k not in body]
        if missing:
            print(f"   FAIL: missing keys {missing}; got {body!r}")
            return False
    print(f"   OK ({r.status_code}): {json.dumps(body, default=str)[:200]}")
    return True


def main() -> int:
    print("=" * 60)
    print("Unified Console e2e smoke test")
    print("=" * 60)

    all_ok = True

    # Per-service liveness
    for name, base in SERVICES.items():
        all_ok &= check(f"{name} healthz", f"{base}/healthz", expect_keys=["status"])

    # Aggregate gateway
    all_ok &= check(
        "xhs-saas /api/v1/health/all",
        f"{SERVICES['xhs-saas']}/api/v1/health/all",
        expect_keys=["status", "services"],
    )

    # Candidates gateway forward (through xhs -> pbp)
    all_ok &= check(
        "gateway pbp /api/v1/pbp/api/candidates/top20",
        f"{SERVICES['xhs-saas']}/api/v1/pbp/api/candidates/top20",
        expect_keys=["items"],
    )

    # Analytics gateway forward (through xhs -> lakehouse)
    all_ok &= check(
        "gateway lakehouse /api/v1/lakehouse/api/kpis",
        f"{SERVICES['xhs-saas']}/api/v1/lakehouse/api/kpis",
        expect_keys=["pv_today", "uv_today", "funnel"],
    )

    # Alerts engine reachable
    all_ok &= check(
        "xhs /api/v1/alerts/recent",
        f"{SERVICES['xhs-saas']}/api/v1/alerts/recent",
        expect_keys=["rules", "event_counters"],
    )

    print("=" * 60)
    if all_ok:
        print("ALL GREEN")
        return 0
    print("FAILURES — see above")
    return 1


if __name__ == "__main__":
    sys.exit(main())