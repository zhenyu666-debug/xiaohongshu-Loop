"""TigerGraph-backed detector — runs the GSQL queries via RESTPP and
post-processes results into :class:`RiskAlert` records.

If the runtime is unreachable the detector returns a :class:`DetectionRun`
with ``status="degraded"`` instead of raising. The frontend in
"demo-without-graph" mode keeps working against :class:`LocalDetector`.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from ..config import Settings, get_settings
from .local_detector import snapshot_from_dataset
from .models import (
    DetectionRun,
    GraphSnapshot,
    RiskAlert,
    betweenness_alert_from_gsql,
    burst_alert_from_gsql,
    closeness_alert_from_gsql,
    jaccard_alert_from_gsql,
    lpcc_alert_from_gsql,
    pagerank_alert_from_gsql,
    ring_alert_from_gsql,
    shared_device_alert_from_gsql,
    wcc_alert_from_gsql,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _post_query(
    client: httpx.Client,
    settings: Settings,
    name: str,
    params: dict[str, Any] | None = None,
) -> dict:
    body = {"graph": settings.tg_graph_name, "params": params or {}}
    r = client.post(f"{settings.restpp_url}/query/{name}", json=body, timeout=30.0)
    r.raise_for_status()
    try:
        return r.json()
    except json.JSONDecodeError:
        return {"results": [], "_raw": r.text}


class TigerGraphDetector:
    """Run every detection query and produce a structured
    :class:`DetectionRun`."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def ping(self) -> bool:
        try:
            with httpx.Client() as c:
                r = c.get(f"{self.settings.restpp_url}/echo", timeout=5.0)
                return r.status_code == 200
        except httpx.HTTPError:
            return False

    def run(self, *, top_k: int = 50) -> DetectionRun:
        started = _now()
        t0 = time.perf_counter()
        alerts: list[RiskAlert] = []
        status = "ok"
        detail_parts: list[str] = []

        try:
            with httpx.Client() as client:
                if not self.ping():
                    raise RuntimeError("TigerGraph RESTPP not reachable")

                # 1) Transaction rings
                try:
                    res = _post_query(
                        client,
                        self.settings,
                        "transactionRings",
                        {"minLen": self.settings.thresh_ring_min_len, "maxLen": 6, "limitPerRing": 50},
                    )
                    a = ring_alert_from_gsql(res)
                    if a:
                        alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"transactionRings={exc}")

                # 2) Shared devices
                try:
                    res = _post_query(
                        client,
                        self.settings,
                        "sharedDeviceRings",
                        {"minShared": self.settings.thresh_shared_device_min, "limitAccounts": 200},
                    )
                    a = shared_device_alert_from_gsql(res)
                    if a:
                        alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"sharedDeviceRings={exc}")

                # 3) Burst transactions
                try:
                    res = _post_query(
                        client,
                        self.settings,
                        "burstTransactions",
                        {
                            "windowMin": self.settings.thresh_burst_tx_window_min,
                            "minCount": self.settings.thresh_burst_tx_count,
                            "limitAccounts": 200,
                        },
                    )
                    a = burst_alert_from_gsql(res)
                    if a:
                        alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"burstTransactions={exc}")

                # 4) Top-K centrality
                try:
                    res = _post_query(
                        client,
                        self.settings,
                        "pageRankAccounts",
                        {"damping": 0.85, "iterations": 25, "topK": top_k},
                    )
                    a = pagerank_alert_from_gsql(res, top_k=top_k)
                    if a:
                        alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"pageRankAccounts={exc}")

                # 5) Weakly Connected Components (entity-resolution helper)
                try:
                    res = _post_query(
                        client,
                        self.settings,
                        "tg_wcc",
                        {
                            "v_type": "Account",
                            "e_type": "SHARES_DEVICE",
                            "max_iter": 10,
                            "print_limit": 100,
                        },
                    )
                    a = wcc_alert_from_gsql(res)
                    if a:
                        alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_wcc={exc}")

                # 6) Community Detection (Label Propagation)
                try:
                    res = _post_query(
                        client,
                        self.settings,
                        "tg_lpcc",
                        {
                            "v_type": "Account",
                            "e_type": "SHARES_DEVICE",
                            "max_iter": 20,
                            "seed": 42,
                            "print_limit": 100,
                        },
                    )
                    a = lpcc_alert_from_gsql(res)
                    if a:
                        alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_lpcc={exc}")

                # 7) Jaccard Similarity (identity-link scoring)
                try:
                    res = _post_query(
                        client,
                        self.settings,
                        "tg_jaccard",
                        {
                            "source_id": "A0",
                            "target_id": "A1",
                            "v_type": "Account",
                            "e_type": "USES_DEVICE",
                            "top_k": top_k,
                        },
                    )
                    a = jaccard_alert_from_gsql(res)
                    if a:
                        alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_jaccard={exc}")

                # 8) Betweenness Centrality (broker / mule detection)
                try:
                    res = _post_query(
                        client,
                        self.settings,
                        "tg_betweenness",
                        {
                            "v_type": "Account",
                            "e_type": "SHARES_DEVICE",
                            "sample_size": 0,
                            "top_k": top_k,
                        },
                    )
                    a = betweenness_alert_from_gsql(res)
                    if a:
                        alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_betweenness={exc}")

                # 9) Closeness Centrality (hub detection)
                try:
                    res = _post_query(
                        client,
                        self.settings,
                        "tg_closeness",
                        {
                            "v_type": "Account",
                            "e_type": "SHARES_DEVICE",
                            "top_k": top_k,
                        },
                    )
                    a = closeness_alert_from_gsql(res)
                    if a:
                        alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_closeness={exc}")

        except Exception as exc:
            status = "degraded" if alerts else "unreachable"
            detail_parts.append(str(exc))

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        ended = _now()
        metrics = {
            "alerts_total": len(alerts),
            "elapsed_ms": elapsed_ms,
        }
        return DetectionRun(
            run_id=str(uuid.uuid4()),
            started_at=started,
            ended_at=ended,
            backend="tigergraph",
            status=status,
            detail="; ".join(detail_parts) or "ok",
            alerts=alerts,
            snapshot=GraphSnapshot(),
            metrics=metrics,
        )


def run_remote_detector(
    fallback_dataset=None, settings: Settings | None = None
) -> DetectionRun:
    """Convenience that returns a TigerGraph result if reachable, otherwise
    falls back to :func:`run_local_detector` over ``fallback_dataset``.
    """
    det = TigerGraphDetector(settings=settings)
    res = det.run()
    if res.status in ("ok", "partial") and res.alerts:
        return res
    if fallback_dataset is not None:
        from .local_detector import run_local_detector

        local = run_local_detector(fallback_dataset)
        # Surface the fallback explicitly
        from dataclasses import replace

        return replace(
            local,
            backend=f"{local.backend}+fallback",
            detail=(
                f"TigerGraph unreachable; served local fallback. {local.detail}"
            ),
        )
    return res