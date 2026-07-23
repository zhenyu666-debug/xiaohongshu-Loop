"""Lightweight APScheduler-based jobs for periodic fraud detection.

The :class:`FundsMonitor` schedules the three funds-flow detectors
(``funds_path_trace`` / ``circular_funds`` / ``burst_amount``) to run on
a configurable interval, build a :class:`RiskAlert` from each, and ship
the consolidated payload to a user-supplied webhook URL — Slack /
Mattermost / DingTalk / 企业微信 / generic JSON sink, all of which accept
the same ``{ "text": ..., "alerts": [...] }`` POST body.

This is intentionally in-process: we reuse the FastAPI event loop,
piggy-back on the existing dataset, and avoid needing a separate broker
(Redis/RabbitMQ) or worker pool.  For heavier workloads we suggest
hooking this to a real external scheduler (k8s CronJob / Cloud Scheduler)
and reading ``STATE['latest_dataset']`` from a JSON dump.
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

import httpx

from ..config import Settings, get_settings
from ..loader.synth_generator import build_dataset
from ..detection.funds_local import (
    find_burst_amount as funds_burst,
    find_circular_funds as funds_circles,
    trace_funds_paths as funds_paths,
)
from ..detection.models import (
    RiskAlert,
    burst_amount_alert_from_gsql,
    circular_funds_alert_from_gsql,
    funds_path_trace_alert_from_gsql,
)

log = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class MonitorConfig:
    interval_minutes: int = 60
    webhook_url: str | None = None
    webhook_token: str | None = None
    dry_run: bool = True
    dataset_seed: int | None = None
    scale_factor: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "interval_minutes": self.interval_minutes,
            "webhook_url": self.webhook_url,
            "dry_run": self.dry_run,
            "dataset_seed": self.dataset_seed,
            "scale_factor": self.scale_factor,
        }


@dataclass
class MonitorStatus:
    running: bool = False
    started_at: str | None = None
    last_run_at: str | None = None
    last_alert_count: int = 0
    last_alert_kinds: list[str] = field(default_factory=list)
    runs_total: int = 0
    runs_failed: int = 0
    config: MonitorConfig = field(default_factory=MonitorConfig)
    last_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "running": self.running,
            "started_at": self.started_at,
            "last_run_at": self.last_run_at,
            "last_alert_count": self.last_alert_count,
            "last_alert_kinds": self.last_alert_kinds,
            "runs_total": self.runs_total,
            "runs_failed": self.runs_failed,
            "config": self.config.to_dict(),
            "last_error": self.last_error,
        }


class FundsMonitor:
    """APScheduler-free background thread that re-runs the funds flow
    detectors every ``interval_minutes`` and POSTs the alerts to a webhook.

    We hand-roll a daemon-thread loop instead of importing ``apscheduler``
    so the project stays air-gapped-friendly (per its pyproject.toml
    optional-deps contract).  Same semantics — periodic + cancellable.
    """

    def __init__(self) -> None:
        self._status = MonitorStatus()
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()

    # ── public API ───────────────────────────────────────────────────────

    def status(self) -> dict[str, Any]:
        return self._status.to_dict()

    def start(
        self,
        *,
        interval_minutes: int = 60,
        webhook_url: str | None = None,
        webhook_token: str | None = None,
        dry_run: bool = True,
        dataset_seed: int | None = None,
        scale_factor: float | None = None,
    ) -> bool:
        if self._thread and self._thread.is_alive():
            log.info("FundsMonitor already running — reconfiguring")
            self._stop_event.set()
            self._thread.join(timeout=2.0)
        self._stop_event.clear()
        self._status = MonitorStatus(
            config=MonitorConfig(
                interval_minutes=interval_minutes,
                webhook_url=webhook_url,
                webhook_token=webhook_token,
                dry_run=dry_run,
                dataset_seed=dataset_seed,
                scale_factor=scale_factor,
            )
        )
        self._status.running = True
        self._status.started_at = _now()
        self._thread = threading.Thread(
            target=self._loop,
            args=(interval_minutes,),
            daemon=True,
            name="funds-monitor",
        )
        self._thread.start()
        return True

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2.0)
        self._status.running = False

    # ── core loop ────────────────────────────────────────────────────────

    def _loop(self, interval_minutes: int) -> None:
        cfg = self._status.config
        interval_s = max(30, int(interval_minutes) * 60)
        log.info("FundsMonitor loop: every %d seconds", interval_s)
        while not self._stop_event.is_set():
            try:
                self._run_once()
            except Exception as exc:  # pragma: no cover — safety net
                log.exception("FundsMonitor tick failed")
                self._status.last_error = str(exc)[:500]
                self._status.runs_failed += 1
            # sleep in 1-s slices so stop() is responsive
            for _ in range(interval_s):
                if self._stop_event.is_set():
                    break
                time.sleep(1.0)

    def _run_once(self) -> dict[str, Any]:
        s = get_settings()
        cfg = self._status.config
        seed = cfg.dataset_seed if cfg.dataset_seed is not None else s.synth_seed

        # Apply scale factor if set
        if cfg.scale_factor is not None and cfg.scale_factor >= 1.0:
            sf = float(cfg.scale_factor)
            accounts     = max(10,      round(1200 * sf))
            devices      = max(5,       round(900  * sf))
            merchants    = max(3,       round(300  * sf))
            transactions = max(100,     round(20000* sf))
            fraud_rings  = max(3,       round(6    * sf))
            ds = build_dataset(
                accounts=accounts, devices=devices, merchants=merchants,
                transactions=transactions, fraud_rings=fraud_rings, seed=seed,
            )
        else:
            ds = build_dataset(seed=seed)

        alerts = run_funds_detectors(ds)

        self._status.last_run_at = _now()
        self._status.last_alert_count = len(alerts)
        self._status.last_alert_kinds = [a.kind for a in alerts]
        self._status.runs_total += 1

        payload = {
            "ok": True,
            "kind": "funds_monitor",
            "ts": self._status.last_run_at,
            "run_id": str(uuid.uuid4()),
            "alerts": [a.to_dict() for a in alerts],
            "alert_count": len(alerts),
        }
        if self._status.config.dry_run:
            log.info("FundsMonitor (dry-run): %d alerts", len(alerts))
        else:
            ok = self._ship_payload(payload)
            log.info(
                "FundsMonitor: %d alerts → webhook %s",
                len(alerts),
                "OK" if ok else "FAIL",
            )
        return payload

    def _ship_payload(self, payload: dict[str, Any]) -> bool:
        url = self._status.config.webhook_url
        if not url:
            log.warning("FundsMonitor: webhook_url not set — skipping POST")
            return False
        headers = {"Content-Type": "application/json"}
        if self._status.config.webhook_token:
            headers["Authorization"] = f"Bearer {self._status.config.webhook_token}"
        try:
            with httpx.Client() as client:
                r = client.post(url, json=payload, headers=headers, timeout=15.0)
            return 200 <= r.status_code < 300
        except httpx.HTTPError as exc:
            log.warning("FundsMonitor webhook POST failed: %s", exc)
            return False


def run_funds_detectors(ds: Any) -> list[RiskAlert]:
    """One-shot run of the 3 funds-flow detectors — pure-Python fallback.

    Independent of the monitor thread; safe to call from CLI / tests.
    """
    alerts: list[RiskAlert] = []
    try:
        circles = funds_circles(ds, min_total=50000.0, max_hops=20, min_hops=3)
        cf = circular_funds_alert_from_gsql(circles)
        if cf:
            alerts.append(cf)
    except Exception:  # pragma: no cover
        pass
    try:
        bursts = funds_burst(ds, burst_factor=5.0)
        ba = burst_amount_alert_from_gsql(bursts)
        if ba:
            alerts.append(ba)
    except Exception:  # pragma: no cover
        pass
    try:
        # Choose a seed: the highest-degree account in the funds-graph.
        from collections import defaultdict

        deg: dict[str, int] = defaultdict(int)
        for r in ds.from_account:
            deg[r["to_id"]] += 1
        for r in ds.to_account:
            deg[r["to_id"]] += 1
        if deg:
            seed = max(deg.items(), key=lambda kv: kv[1])[0]
            paths = funds_paths(ds, start_id=seed, max_hops=20, max_paths=200)
            pt = funds_path_trace_alert_from_gsql(paths)
            if pt:
                alerts.append(pt)
    except Exception:  # pragma: no cover
        pass
    return alerts


# Module-level singleton (used by FastAPI dependency lookups)
_monitor: FundsMonitor | None = None
_monitor_lock = threading.Lock()


def get_monitor() -> FundsMonitor:
    global _monitor
    with _monitor_lock:
        if _monitor is None:
            _monitor = FundsMonitor()
        return _monitor
