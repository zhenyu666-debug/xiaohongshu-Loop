"""Gateway-only smoke test.

Hits the three core health endpoints via the xhs-saas gateway to confirm the
service chain is wired correctly. Does NOT touch Chromium / cookies /
publishing. Use this whenever you just need to verify "xhs-saas can reach
pbp-api and lakehouse-api via the proxy".

Ports (must match scripts/console_gui.py and app/core/config.py):
  xhs-saas      8080   -> /api/v1/health/all   (aggregated, single endpoint)
  pbp-api       8090   -> /healthz (proxied from /api/v1/health/all)
  lakehouse-api 8091   -> /healthz (proxied from /api/v1/health/all)

Usage:
    python scripts/gateway_smoke.py
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request

GATEWAY = "http://127.0.0.1:8080"


def _http_json(url, timeout=5.0):
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def check_health_all():
    url = f"{GATEWAY}/api/v1/health/all"
    data = _http_json(url, timeout=10)
    services = data.get("services", [])
    rc = 0
    for svc in services:
        ok = svc.get("status") == "up"
        marker = "PASS" if ok else "FAIL"
        lat = svc.get("latency_ms")
        print(f"[{marker}] {svc.get('name'):<12} status={svc.get('status'):<8} latency_ms={lat}")
        if not ok:
            rc = 1
    overall = data.get("status", "unknown")
    print(f"overall: {overall}")
    return rc


def check_pbp_candidates_proxy():
    """A cold call to pbp via gateway can take 1-3s; allow 15s."""
    url = f"{GATEWAY}/api/v1/pbp/candidates?limit=1"
    try:
        data = _http_json(url, timeout=15.0)
    except urllib.error.URLError as exc:
        print(f"[FAIL] gateway -> pbp-api /api/candidates: {exc}")
        return 1
    n = len(data.get("items", []))
    if n == 0:
        print("[FAIL] gateway -> pbp-api /api/candidates: 0 items")
        return 1
    print(f"[PASS] gateway -> pbp-api /api/candidates: {n} item(s), first id={data['items'][0].get('id')}")
    return 0


def main():
    print(f"Gateway smoke target: {GATEWAY}")
    rc1 = check_health_all()
    rc2 = check_pbp_candidates_proxy()
    rc = rc1 or rc2
    if rc == 0:
        print("\nALL GATEWAY SMOKE CHECKS PASSED")
    else:
        print("\nFAILED -- see markers above")
    return rc


if __name__ == "__main__":
    sys.exit(main())