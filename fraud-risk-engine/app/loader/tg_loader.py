"""TigerGraph loader — schema management, query installation, data upload.

The loader is intentionally tolerant: if TigerGraph is not reachable, every
operation returns a structured :class:`LoaderResult` with ``status="degraded"``
rather than raising. This keeps the FastAPI service usable in
"demo-without-graph" mode for the frontend and for unit tests.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

import httpx

from ..config import Settings, get_settings
from ..queries import (
    GSQL_BURST_TRANSACTIONS,
    GSQL_PAGERANK_ACCOUNTS,
    GSQL_SHARED_DEVICE_RINGS,
    GSQL_TRANSACTION_RINGS,
)
from ..schema import GSQL_SCHEMA
from .synth_generator import GeneratedDataset

log = logging.getLogger(__name__)


@dataclass
class LoaderResult:
    """Structured result from a loader operation."""

    ok: bool
    status: str = "ok"
    detail: str = ""
    payload: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {
            "ok": self.ok,
            "status": self.status,
            "detail": self.detail,
            "payload": self.payload,
        }


# ---------------------------------------------------------------------------
# Low-level HTTP helpers
# ---------------------------------------------------------------------------


def _request_with_retry(
    client: httpx.Client, method: str, url: str, *, retries: int = 3, **kwargs
) -> httpx.Response:
    last_exc: Exception | None = None
    for attempt in range(retries):
        try:
            resp = client.request(method, url, timeout=10.0, **kwargs)
            if resp.status_code < 500:
                return resp
            log.warning("TG %s %s -> %s (attempt %d)", method, url, resp.status_code, attempt + 1)
        except httpx.HTTPError as exc:  # pragma: no cover - network dependent
            last_exc = exc
            log.warning("TG %s %s failed: %s (attempt %d)", method, url, exc, attempt + 1)
        time.sleep(0.4 * (attempt + 1))
    if last_exc:
        raise last_exc
    raise httpx.HTTPError(f"All retries failed for {method} {url}")


def ping(settings: Settings | None = None) -> LoaderResult:
    """Health-check the TigerGraph RESTPP endpoint."""
    s = settings or get_settings()
    url = f"{s.restpp_url}/echo"
    try:
        with httpx.Client() as client:
            r = _request_with_retry(client, "GET", url)
        return LoaderResult(
            ok=r.status_code == 200,
            status="ok" if r.status_code == 200 else "degraded",
            detail=f"HTTP {r.status_code}",
            payload={"echo": r.text.strip()} if r.status_code == 200 else {},
        )
    except Exception as exc:
        return LoaderResult(ok=False, status="unreachable", detail=str(exc))


# ---------------------------------------------------------------------------
# Schema + queries
# ---------------------------------------------------------------------------


def _post_gsql(client: httpx.Client, settings: Settings, gsql: str) -> LoaderResult:
    url = f"{s.restpp_url}/gsqlserver/gsql"
    try:
        r = client.post(url, content=gsql, timeout=30.0)
        ok = r.status_code == 200 and '"error"' not in r.text.lower()
        return LoaderResult(
            ok=ok,
            status="ok" if ok else "degraded",
            detail=r.text.strip()[:500],
        )
    except httpx.HTTPError as exc:
        return LoaderResult(ok=False, status="unreachable", detail=str(exc))


def ensure_schema(settings: Settings | None = None) -> LoaderResult:
    """Create the FraudRisk graph + vertex + edge schema (idempotent)."""
    s = settings or get_settings()
    gsql = (
        "DROP GRAPH FraudRisk IF EXISTS;\n"
        f"{GSQL_SCHEMA}\n"
    )
    try:
        with httpx.Client() as client:
            return _post_gsql(client, s, gsql)
    except Exception as exc:
        return LoaderResult(ok=False, status="unreachable", detail=str(exc))


def install_queries(settings: Settings | None = None) -> LoaderResult:
    """INSTALL every GSQL fraud-detection query."""
    s = settings or get_settings()
    queries = [
        GSQL_TRANSACTION_RINGS,
        GSQL_SHARED_DEVICE_RINGS,
        GSQL_BURST_TRANSACTIONS,
        GSQL_PAGERANK_ACCOUNTS,
    ]
    results: list[dict] = []
    try:
        with httpx.Client() as client:
            for q in queries:
                res = _post_gsql(client, s, q)
                results.append({"query": q.split("\n", 1)[0][:60], **res.as_dict()})
        ok = all(r["ok"] for r in results)
        return LoaderResult(
            ok=ok,
            status="ok" if ok else "partial",
            detail="; ".join(f"{r['query']}={r['status']}" for r in results),
            payload={"queries": results},
        )
    except Exception as exc:
        return LoaderResult(ok=False, status="unreachable", detail=str(exc))


# ---------------------------------------------------------------------------
# Data upload
# ---------------------------------------------------------------------------


def upsert_vertices(
    settings: Settings | None, vertex_type: str, rows: Iterable[dict]
) -> LoaderResult:
    """POST a JSON list to ``/graph/{graph}/{vertex}`` via RESTPP upsert."""
    s = settings or get_settings()
    url = f"{s.restpp_url}/graph/{s.tg_graph_name}/{vertex_type}"
    payload = list(rows)
    if not payload:
        return LoaderResult(ok=True, status="ok", detail="no rows")
    try:
        with httpx.Client() as client:
            r = client.post(url, json=payload, timeout=30.0)
        ok = r.status_code in (200, 201, 202)
        return LoaderResult(
            ok=ok,
            status="ok" if ok else "degraded",
            detail=f"HTTP {r.status_code}: {r.text.strip()[:200]}",
            payload={"uploaded": len(payload)},
        )
    except httpx.HTTPError as exc:
        return LoaderResult(ok=False, status="unreachable", detail=str(exc))


def upsert_edges(
    settings: Settings | None, edge_type: str, rows: Iterable[dict]
) -> LoaderResult:
    """POST edges to ``/graph/{graph}/{edge}`` (TigerGraph expects
    ``{"vertices": {...}, "edges": {...}}``)."""
    s = settings or get_settings()
    if not rows:
        return LoaderResult(ok=True, status="ok", detail="no rows")
    url = f"{s.restpp_url}/graph/{s.tg_graph_name}/{edge_type}"
    body = {"edges": list(rows)}
    try:
        with httpx.Client() as client:
            r = client.post(url, json=body, timeout=60.0)
        ok = r.status_code in (200, 201, 202)
        return LoaderResult(
            ok=ok,
            status="ok" if ok else "degraded",
            detail=f"HTTP {r.status_code}: {r.text.strip()[:200]}",
            payload={"uploaded": len(rows)},
        )
    except httpx.HTTPError as exc:
        return LoaderResult(ok=False, status="unreachable", detail=str(exc))


def load_dataset(
    ds: GeneratedDataset, settings: Settings | None = None
) -> LoaderResult:
    """Upload a generated dataset into TigerGraph. Returns an aggregated
    :class:`LoaderResult` whose payload summarises per-stage status."""
    s = settings or get_settings()
    stages: list[dict] = []

    # Vertices
    vertex_plan = [
        ("Customer", ds.customers),
        ("Account", ds.accounts),
        ("Card", ds.cards),
        ("Device", ds.devices),
        ("IP", ds.ips),
        ("Merchant", ds.merchants),
        ("Transaction", ds.transactions),
    ]
    for vtype, rows in vertex_plan:
        stages.append({"stage": f"vertex:{vtype}", **upsert_vertices(s, vtype, rows).as_dict()})

    # Edges
    edge_plan = [
        ("OWNS", ds.owns),
        ("HAS_CARD", ds.has_card),
        ("USES_DEVICE", ds.uses_device),
        ("LOGGED_FROM", ds.logged_from),
        ("PAID_TO", ds.paid_to),
        ("FROM_ACCOUNT", ds.from_account),
        ("TO_ACCOUNT", ds.to_account),
        ("SHARES_DEVICE", ds.shares_device),
        ("SHARES_IP", ds.shares_ip),
    ]
    for etype, rows in edge_plan:
        stages.append({"stage": f"edge:{etype}", **upsert_edges(s, etype, rows).as_dict()})

    ok = all(st["ok"] for st in stages)
    return LoaderResult(
        ok=ok,
        status="ok" if ok else "partial",
        detail=f"{sum(1 for st in stages if st['ok'])}/{len(stages)} stages ok",
        payload={"stages": stages, "counts": ds.counts()},
    )


def export_seed_files(ds: GeneratedDataset, root: Path | str) -> dict[str, int]:
    """Persist the generated dataset as on-disk artefacts (JSONL bundles +
    CSV) under ``root``. Returns counts per artefact."""
    root = Path(root)
    from .synth_generator import dataset_to_csv_bundles, dataset_to_jsonl_bundles

    jsonl_counts = dataset_to_jsonl_bundles(ds, root / "jsonl")
    csv_counts = dataset_to_csv_bundles(ds, root / "csv")
    manifest = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "jsonl": jsonl_counts,
        "csv": csv_counts,
        "totals": ds.counts(),
        "planted_rings": ds.planted_rings,
    }
    (root / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return jsonl_counts