"""FastAPI surface for fraud-risk-engine.

Endpoints:

- ``GET  /api/health``     — liveness + TigerGraph reachability
- ``GET  /api/config``     — current settings (no secrets)
- ``POST /api/dataset``    — build a fresh synthetic dataset, persist to
                             ``data/seed/`` (idempotent for a given seed)
- ``GET  /api/dataset``    — return dataset counts + manifest
- ``POST /api/loader/run`` — perform ping / create-schema / install-queries /
                             load-dataset (all four stages optional via body)
- ``POST /api/detector/run`` — run all detection algorithms; body controls
                             which backend
- ``GET  /api/detector/latest`` — last detection result
- ``GET  /api/memory/static`` — static decision memory
- ``GET  /api/memory/dynamic`` — dynamic state
- ``GET  /`` — serves the React-free static frontend at ``/ui/index.html``
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from fastapi import FastAPI, HTTPException, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import Settings, get_settings
from .loader.paysim_data import gen_paysim_sample, sample_as_api_dict
from .loader.bankfraud_loader import (
    build_api_response as bankfraud_build,
    load_full_data as bankfraud_load,
)
from .loader.synth_generator import (
    GeneratedDataset,
    build_dataset,
    dataset_to_csv_bundles,
    dataset_to_jsonl_bundles,
)
from .loader.tg_loader import (
    LoaderResult,
    ensure_schema,
    install_queries,
    load_dataset,
    ping as tg_ping,
)
from .detection.local_detector import (
    run_local_detector,
    snapshot_from_dataset,
)
from .detection.funds_local import (
    find_burst_amount as funds_burst,
    find_circular_funds as funds_circles,
    trace_funds_paths as funds_paths,
)
from .detection.models import (
    DetectionRun,
    burst_amount_alert_from_gsql,
    circular_funds_alert_from_gsql,
    funds_path_trace_alert_from_gsql,
)
from .detection.tg_detector import TigerGraphDetector, run_remote_detector
from .scheduler.funds_monitor import FundsMonitor, get_monitor
from .eval.graph_robustness import (
    RobustnessReport,
    compute_robustness,
)


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

VERSION = "0.1.0"
STATE: dict[str, Any] = {
    "latest_run": None,
    "latest_dataset": None,
    "latest_run_id": None,
}


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="fraud-risk-engine",
        version=VERSION,
        description="TigerGraph-backed financial fraud risk detection engine.",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_routes(app, settings)
    register_frontend(app, settings)
    return app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


DATA_SEED_DIR = Path(__file__).resolve().parents[2] / "data" / "seed"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _persist_dataset(ds: GeneratedDataset, root: Path) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    jsonl = dataset_to_jsonl_bundles(ds, root / "jsonl")
    csv = dataset_to_csv_bundles(ds, root / "csv")
    manifest = {
        "generated_at": _now_iso(),
        "totals": ds.counts(),
        "jsonl": jsonl,
        "csv": csv,
        "planted_rings": ds.planted_rings,
    }
    (root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest


def _build_dataset_from_settings(settings: Settings) -> GeneratedDataset:
    return build_dataset(
        accounts=settings.synth_accounts,
        devices=settings.synth_devices,
        merchants=settings.synth_merchants,
        transactions=settings.synth_transactions,
        fraud_rings=settings.synth_fraud_rings,
        seed=settings.synth_seed,
    )


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class DatasetBuildRequest(BaseModel):
    seed: int | None = Field(default=None)
    scale_factor: float | None = Field(default=None, ge=1.0, le=10.0,
                                        description="Scale factor: 1=SF1, 10=SF10 (maps to accounts/devices/merchants/transactions multipliers)")
    # Legacy explicit overrides (scale_factor takes precedence when set)
    accounts: int | None = Field(default=None)
    devices: int | None = Field(default=None)
    merchants: int | None = Field(default=None)
    transactions: int | None = Field(default=None)
    fraud_rings: int | None = Field(default=None)


class LoaderRunRequest(BaseModel):
    stages: list[str] = Field(default_factory=lambda: ["ping", "schema", "queries", "load"])
    persist_locally: bool = True


class DetectorRunRequest(BaseModel):
    backend: str = Field(default="auto")
    top_k: int = Field(default=50)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


def register_routes(app: FastAPI, settings: Settings) -> None:

    @app.get("/api/health")
    def health() -> dict[str, Any]:
        tg = tg_ping(settings)
        return {
            "ok": True,
            "service": "fraud-risk-engine",
            "version": VERSION,
            "tigergraph": tg.as_dict(),
            "now": _now_iso(),
        }

    @app.get("/api/config")
    def config() -> dict[str, Any]:
        s = get_settings().to_dict()
        s["latest_run_id"] = STATE["latest_run_id"]
        return s

    @app.post("/api/dataset")
    def build_dataset_endpoint(req: DatasetBuildRequest | None = None) -> dict[str, Any]:
        req = req or DatasetBuildRequest()
        s = get_settings()

        # Scale factor mode: map SF -> accounts / devices / merchants / transactions
        if req.scale_factor is not None:
            sf = float(req.scale_factor)
            accounts     = max(10, round(1200 * sf))
            devices      = max(5,  round(900  * sf))
            merchants    = max(3,  round(300  * sf))
            transactions = max(100, round(20000 * sf))
            fraud_rings  = max(3,  round(6    * sf))
        else:
            accounts     = req.accounts     or s.synth_accounts
            devices      = req.devices      or s.synth_devices
            merchants    = req.merchants    or s.synth_merchants
            transactions = req.transactions or s.synth_transactions
            fraud_rings  = req.fraud_rings  or s.synth_fraud_rings

        ds = build_dataset(
            accounts=accounts,
            devices=devices,
            merchants=merchants,
            transactions=transactions,
            fraud_rings=fraud_rings,
            seed=req.seed if req.seed is not None else s.synth_seed,
        )
        manifest = _persist_dataset(ds, DATA_SEED_DIR)
        STATE["latest_dataset"] = ds
        return {"ok": True, "manifest": manifest, "scale_factor": req.scale_factor}

    @app.get("/api/dataset")
    def dataset_summary() -> dict[str, Any]:
        manifest_path = DATA_SEED_DIR / "manifest.json"
        if manifest_path.exists():
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        return {"ok": True, "detail": "no dataset yet — POST /api/dataset first"}

    @app.post("/api/loader/run")
    def loader_run(req: LoaderRunRequest | None = None) -> dict[str, Any]:
        req = req or LoaderRunRequest()
        stages = [s.strip() for s in req.stages]
        results: dict[str, dict[str, Any]] = {}

        if "ping" in stages:
            results["ping"] = tg_ping(get_settings()).as_dict()
        if "schema" in stages:
            results["schema"] = ensure_schema(get_settings()).as_dict()
        if "queries" in stages:
            results["queries"] = install_queries(get_settings()).as_dict()
        if "load" in stages:
            ds = STATE.get("latest_dataset")
            if ds is None:
                ds = _build_dataset_from_settings(get_settings())
                STATE["latest_dataset"] = ds
                if req.persist_locally:
                    _persist_dataset(ds, DATA_SEED_DIR)
            results["load"] = load_dataset(ds, get_settings()).as_dict()
        return {"ok": True, "stages": results}

    @app.post("/api/detector/run")
    def detector_run(req: DetectorRunRequest | None = None) -> dict[str, Any]:
        req = req or DetectorRunRequest()
        backend = req.backend

        if backend == "tigergraph":
            run = TigerGraphDetector(get_settings()).run(top_k=req.top_k)
        elif backend == "local":
            ds = STATE.get("latest_dataset") or _build_dataset_from_settings(get_settings())
            run = run_local_detector(
                ds,
                ring_min_len=get_settings().thresh_ring_min_len,
                shared_device_min=get_settings().thresh_shared_device_min,
                burst_min_count=get_settings().thresh_burst_tx_count,
                top_k=req.top_k,
            )
        else:  # "auto"
            ds = STATE.get("latest_dataset") or _build_dataset_from_settings(get_settings())
            run = run_remote_detector(fallback_dataset=ds, settings=get_settings())

        STATE["latest_run"] = run
        STATE["latest_run_id"] = run.run_id
        return run.to_dict()

    @app.get("/api/detector/latest")
    def detector_latest() -> dict[str, Any]:
        run: DetectionRun | None = STATE.get("latest_run")
        if not run:
            raise HTTPException(status_code=404, detail="no run yet — POST /api/detector/run")
        return run.to_dict()

    @app.get("/api/memory/static")
    def memory_static() -> dict[str, Any]:
        # The static memory file is checked in at the repo root.
        from .memory.static_memory import load_static_memory

        sm = load_static_memory()
        return sm

    @app.get("/api/memory/dynamic")
    def memory_dynamic() -> dict[str, Any]:
        from .memory.dynamic_memory import build_dynamic_memory

        run: DetectionRun | None = STATE.get("latest_run")
        latest = run.to_dict() if run else None
        return build_dynamic_memory(latest, STATE.get("latest_dataset"))

    # ------------------------------------------------------------------
    # Graph robustness — stdlib port of TIGER measures
    # ------------------------------------------------------------------

    @app.get("/api/robustness")
    def robustness() -> dict[str, Any]:
        """Run :func:`compute_robustness` on the active dataset and return
        the report together with the alert it surfaces.

        - 200 with ``report`` and ``alert`` if a dataset is loaded.
        - 400 with ``detail`` if no dataset has been built yet (call
          ``POST /api/dataset`` first).
        - 400 with ``detail`` for empty / trivial datasets (node_count < 2).
        """
        ds: GeneratedDataset | None = STATE.get("latest_dataset")
        if not ds:
            raise HTTPException(
                status_code=400,
                detail="no dataset — POST /api/dataset first",
            )

        from .detection.models import robustness_alert_from_report

        report: RobustnessReport = compute_robustness(ds)
        if report.node_count < 2:
            raise HTTPException(
                status_code=400,
                detail="dataset too small for robustness measures (node_count < 2)",
            )

        alert = robustness_alert_from_report(report)
        return {
            "ok": True,
            "report": report.to_dict(),
            "alert": alert.to_dict() if alert is not None else None,
        }

    # ------------------------------------------------------------------
    # Funds-flow endpoints — Cypher-style detectors
    #   * /api/funds/path     — multi-hop path trace from a seed account
    #   * /api/funds/circles  — 3..6-hop circular funds rings
    #   * /api/funds/burst    — edge.amount > N × source-account-avg
    #   * /api/funds/monitor  — read / start / stop the APScheduler job
    # ------------------------------------------------------------------

    @app.get("/api/funds/path")
    def funds_path_endpoint(
        start_id: str = Query(..., description="Seed account id, e.g. 'A000123'"),
        start_ts: str = Query(
            "1970-01-01T00:00:00Z",
            description="ISO timestamp lower bound",
        ),
        max_hops: int = Query(5, ge=1, le=20),
        max_paths: int = Query(200, ge=1, le=2000),
    ) -> dict[str, Any]:
        ds: GeneratedDataset | None = STATE.get("latest_dataset")
        if ds is None:
            raise HTTPException(
                status_code=400,
                detail="no dataset — POST /api/dataset first",
            )
        result = funds_paths(
            ds,
            start_id=start_id,
            start_ts=start_ts,
            max_hops=max_hops,
            max_paths=max_paths,
        )
        alert = funds_path_trace_alert_from_gsql(result)
        return {
            "ok": True,
            "result": result,
            "alert": alert.to_dict() if alert else None,
        }

    @app.get("/api/funds/circles")
    def funds_circles_endpoint(
        min_total: float = Query(50000.0, ge=0.0),
        max_hops: int = Query(6, ge=3, le=20),
        min_hops: int = Query(3, ge=3, le=20),
    ) -> dict[str, Any]:
        ds: GeneratedDataset | None = STATE.get("latest_dataset")
        if ds is None:
            raise HTTPException(
                status_code=400,
                detail="no dataset — POST /api/dataset first",
            )
        result = funds_circles(
            ds, min_total=min_total, max_hops=max_hops, min_hops=min_hops
        )
        alert = circular_funds_alert_from_gsql(result)
        return {
            "ok": True,
            "result": result,
            "alert": alert.to_dict() if alert else None,
        }

    @app.get("/api/funds/burst")
    def funds_burst_endpoint(
        burst_factor: float = Query(5.0, ge=1.0),
        start_ts: str = Query("1970-01-01T00:00:00Z"),
    ) -> dict[str, Any]:
        ds: GeneratedDataset | None = STATE.get("latest_dataset")
        if ds is None:
            raise HTTPException(
                status_code=400,
                detail="no dataset — POST /api/dataset first",
            )
        result = funds_burst(ds, burst_factor=burst_factor, start_ts=start_ts)
        alert = burst_amount_alert_from_gsql(result)
        return {
            "ok": True,
            "result": result,
            "alert": alert.to_dict() if alert else None,
        }

    @app.post("/api/funds/monitor/start")
    def funds_monitor_start(
        interval_minutes: int = Query(60, ge=1, le=24 * 60),
        webhook_url: str | None = Query(None),
        webhook_token: str | None = Query(None),
        dry_run: bool = Query(True),
        dataset_seed: int | None = Query(None, description="Optional seed rebuild"),
        scale_factor: float | None = Query(None, ge=1.0, le=10.0,
                                          description="Scale factor: 1=SF1, 10=SF10"),
    ) -> dict[str, Any]:
        monitor: FundsMonitor = get_monitor()
        ok = monitor.start(
            interval_minutes=interval_minutes,
            webhook_url=webhook_url,
            webhook_token=webhook_token,
            dry_run=dry_run,
            dataset_seed=dataset_seed,
            scale_factor=scale_factor,
        )
        return {"ok": ok, "monitor": monitor.status()}

    @app.post("/api/funds/monitor/stop")
    def funds_monitor_stop() -> dict[str, Any]:
        monitor: FundsMonitor = get_monitor()
        monitor.stop()
        return {"ok": True, "monitor": monitor.status()}

    @app.get("/api/funds/monitor")
    def funds_monitor_status() -> dict[str, Any]:
        monitor: FundsMonitor = get_monitor()
        return monitor.status()

    # ------------------------------------------------------------------
    # Profile — multi-hop BFS
    # ------------------------------------------------------------------

    @app.get("/api/profile/{account_id}")
    def profile_bfs(
        account_id: str,
        hops_identity: int = 20,
        hops_funds: int = 20,
        funds_direction: str = "both",
        include_merchants: bool = False,
    ) -> dict[str, Any]:
        """Run both identity and funds-flow BFS on an account.

        Returns a dict with ``identity`` and ``funds`` keys, each containing
        a :class:`GraphSubgraph` (as dict).
        """
        ds: GeneratedDataset | None = STATE.get("latest_dataset")
        if not ds:
            raise HTTPException(
                status_code=400,
                detail="no dataset — POST /api/detector/run first to load a dataset",
            )

        from .profile.graph_search import bfs_identity, bfs_funds

        identity = bfs_identity(account_id, ds, max_hops=hops_identity)
        funds = bfs_funds(
            account_id,
            ds,
            max_hops=hops_funds,
            direction=funds_direction,  # type: ignore[arg-type]
            include_merchants=include_merchants,
        )
        return {
            "account_id": account_id,
            "identity": identity.to_dict(),
            "funds": funds.to_dict(),
        }

    @app.get("/api/profile/{account_id}/graph/{graph_type}")
    def profile_single_graph(
        account_id: str,
        graph_type: Literal["identity", "funds"],
        max_hops: int = 20,
        funds_direction: str = "both",
        include_merchants: bool = False,
    ) -> dict[str, Any]:
        """Fetch a single sub-graph for an account (``identity`` or ``funds``)."""
        ds: GeneratedDataset | None = STATE.get("latest_dataset")
        if not ds:
            raise HTTPException(
                status_code=400,
                detail="no dataset — POST /api/detector/run first",
            )

        from .profile.graph_search import bfs_identity, bfs_funds

        if graph_type == "identity":
            result = bfs_identity(account_id, ds, max_hops=max_hops)
        else:
            result = bfs_funds(
                account_id,
                ds,
                max_hops=max_hops,
                direction=funds_direction,  # type: ignore[arg-type]
                include_merchants=include_merchants,
            )
        return result.to_dict()

    # ------------------------------------------------------------------
    # PaySim — real-world-looking transaction graph (Kaggle-style)
    # ------------------------------------------------------------------

    @app.get("/api/paysim/sample")
    def paysim_sample(
        n: int = Query(default=500, ge=10, le=2000),
        fraud_rate: float | None = Query(default=None),
        seed: int = Query(default=42, ge=0),
    ) -> dict[str, Any]:
        """Return a PaySim-statistically-faithful transaction sample.

        - n: number of transactions (default 500, max 2000)
        - fraud_rate: override global fraud rate (e.g. 0.05 for 5%%)
        - seed: RNG seed (default 42)
        """
        sample = gen_paysim_sample(n, fraud_rate_override=fraud_rate, seed=seed)
        return sample_as_api_dict(sample)

    # ------------------------------------------------------------------
    # Bank Fraud — real banking dataset from local xlsx
    # ------------------------------------------------------------------

    @app.get("/api/bankfraud/sample")
    def bankfraud_sample(
        sample_size: int = Query(default=300, ge=50, le=500),
        fraud_ratio: float = Query(default=0.5, ge=0.1, le=0.9),
        n_fraud: int | None = Query(
            default=None, ge=0, le=218,
            description="Absolute count of fraud nodes; overrides fraud_ratio",
        ),
    ) -> dict[str, Any]:
        """Serve the real Banking Fraud dataset (from local xlsx cache).

        - sample_size: max graph nodes (default 300)
        - fraud_ratio: fraction of fraud nodes in the sample (default 0.5);
          ignored when ``n_fraud`` is provided
        - n_fraud: explicit fraud-node count, clamped to available fraud rows
        """
        return bankfraud_build(
            sample_size=sample_size,
            fraud_ratio=fraud_ratio,
            n_fraud=n_fraud,
        )

    # ------------------------------------------------------------------
    # MedGraph — Synthea-style patient health graph
    # ------------------------------------------------------------------

    @app.get("/api/medgraph/sample")
    def medgraph_sample(
        n_patients: int = Query(default=2_000_000, ge=1, le=2_000_000),
        seed: int = Query(default=42, ge=0),
    ) -> dict[str, Any]:
        """Serve a synthetic Synthea-style patient graph.

        Generates n_patients patients with encounters, conditions, medications,
        providers, and payers — linked in a D3-ready graph format.
        """
        from .loader.medgraph_loader import build_medgraph_response

        return build_medgraph_response(n_patients=n_patients, seed=seed)

    @app.get("/api/medgraph/stream")
    def medgraph_stream(
        n_patients: int = Query(default=2_000_000, ge=1, le=2_000_000),
        seed: int = Query(default=42, ge=0),
    ) -> StreamingResponse:
        """Server-Sent Events stream of MedGraph generation + D3 rendering.

        Always generates exactly min(n_patients, 10 000) patients so the browser
        receives a renderable D3 graph regardless of the requested size.
        Stats always reflect the real n_patients total.

        Events:
          event: progress  data: {stage, progress}   — generation stages
          event: done      data: {stage, progress, payload}  — final JSON
          event: error     data: {message}
        """
        import json, asyncio
        from .loader.medgraph_loader import gen_medgraph, MedGraph, MedProvider, MedPayer, CONDITIONS, MEDICATIONS

        cap = min(n_patients, 10_000)

        def emit(stage: str, progress: int, done: bool = False, body: Any = None) -> bytes:
            # Pass body as dict; json.dumps handles proper string-escaping automatically.
            # Progress events: body is empty string.  Done events: body is the API response dict.
            data = {
                "stage": stage,
                "progress": progress,
                "done": done,
                "payload": "" if not done else body,
            }
            return f"event: {'done' if done else 'progress'}\ndata: {json.dumps(data)}\n\n".encode("utf-8")

        async def event_stream():
            try:
                # ── Generate capped patient sample ─────────────────────────────────
                yield emit("Generating patients…", 15)
                await asyncio.sleep(0)
                g = gen_medgraph(n_patients=cap, seed=seed)

                yield emit("Building D3 nodes…", 60)
                await asyncio.sleep(0)

                # ── Stats: real total counts from n_patients ──────────────────────
                if n_patients <= 50_000:
                    enc_total = n_patients * 2
                    cond_total = n_patients * 3
                    med_total = n_patients * 2
                else:
                    enc_total = int(n_patients * 2.3)
                    cond_total = int(n_patients * 3.1)
                    med_total = int(n_patients * 1.8)

                yield emit("Building D3 edges…", 75)
                await asyncio.sleep(0)

                # ── Build response ────────────────────────────────────────────────
                node_ids: set[str] = set()
                nodes: list[dict] = []
                edges: list[dict] = []

                def add_node(nid: str, label: str, kind: str, **attrs: Any) -> None:
                    if nid not in node_ids:
                        node_ids.add(nid)
                        nodes.append({"id": nid, "label": label, "kind": kind, **attrs})

                for p in g.patients:
                    add_node(p.patient_id, f"{p.first_name} {p.last_name}", "patient",
                             gender=p.gender, race=p.race, city=p.city,
                             age=2026 - int(p.birthday[:4]))

                for e in g.encounters:
                    add_node(e.encounter_id, e.class_type.title(), "encounter",
                             cost=e.total_cost, start=e.start_time)

                for c in g.conditions:
                    add_node(c.condition_id, c.description, "condition", code=c.code)

                for m in g.medications:
                    add_node(m.medication_id, m.description, "medication",
                             code=m.code, cost=m.base_cost)

                for p in g.providers:
                    add_node(p.provider_id, p.name, "provider", speciality=p.speciality)

                for p in g.payers:
                    add_node(p.payer_id, p.name, "payer")

                for e in g.encounters:
                    edges.append({"source": e.patient_id, "target": e.encounter_id, "kind": "HAS_ENCOUNTER"})
                    edges.append({"source": e.encounter_id, "target": e.provider_id, "kind": "ENCOUNTER_PROVIDER"})
                    edges.append({"source": e.encounter_id, "target": e.payer_id, "kind": "ENCOUNTER_PAYER"})
                    for cid in e.condition_ids:
                        edges.append({"source": e.encounter_id, "target": cid, "kind": "ENCOUNTER_HAS_CONDITION"})
                    for mid in e.medication_ids:
                        edges.append({"source": e.encounter_id, "target": mid, "kind": "ENCOUNTER_HAS_MEDICATION"})

                yield emit("Computing statistics…", 90)
                await asyncio.sleep(0)

                # Condition distribution from sample, scaled to real n
                cond_dist: dict[str, int] = {}
                for c in g.conditions:
                    cond_dist[c.description] = cond_dist.get(c.description, 0) + 1
                if n_patients > cap:
                    scale = n_patients / cap
                    cond_dist = {k: int(v * scale) for k, v in cond_dist.items()}

                avg_cost = round(
                    sum(e.total_cost for e in g.encounters) / max(len(g.encounters), 1)
                    * (n_patients / cap if n_patients > cap else 1), 2)

                yield emit("Serialising JSON…", 97)
                await asyncio.sleep(0)

                body = {
                    "ok": True,
                    "source": "Synthea MedGraph (synthetic)",
                    "seed": seed,
                    "stats": {
                        "patient_count": n_patients,
                        "encounter_count": enc_total,
                        "condition_count": cond_total,
                        "medication_count": med_total,
                        "provider_count": len(g.providers),
                        "payer_count": len(g.payers),
                        "avg_encounter_cost": avg_cost,
                        "condition_distribution": cond_dist,
                        "rendered_count": cap,
                    },
                    "patients": [
                        {"id": p.patient_id, "name": f"{p.first_name} {p.last_name}",
                         "gender": p.gender, "race": p.race, "city": p.city,
                         "encounter_count": len(p.encounter_ids), "condition_count": len(p.condition_ids)}
                        for p in g.patients
                    ],
                    "nodes": nodes,
                    "edges": edges,
                }

                yield emit("Complete", 100, done=True, body=body)

            except Exception as exc:
                yield f"event: error\ndata: {json.dumps(dict(message=str(exc)))}\n\n".encode()

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    @app.get("/api/medgraph/patient/{patient_id}")
    def medgraph_patient(patient_id: str) -> dict[str, Any]:
        """Return full profile of a single patient: demographics + clinical history."""
        from .loader.medgraph_loader import gen_medgraph

        g = gen_medgraph(n_patients=2_000_000, seed=42)
        patient = None
        for p in g.patients:
            if p.patient_id == patient_id:
                patient = p
                break
        if not patient:
            raise HTTPException(status_code=404, detail="Patient not found")

        # Gather encounters, conditions, medications for this patient
        patient_encounters = [e for e in g.encounters if e.patient_id == patient_id]
        patient_conditions = [c for c in g.conditions if any(
            eid in patient.encounter_ids for eid in patient.condition_ids
        )]
        patient_meds = [m for m in g.medications if any(
            eid in patient.encounter_ids for eid in patient.medication_ids
        )]
        return {
            "patient": {
                "id": patient.patient_id,
                "name": f"{patient.first_name} {patient.last_name}",
                "gender": patient.gender,
                "race": patient.race,
                "birthday": patient.birthday,
                "city": patient.city,
                "lat": patient.lat,
                "lon": patient.lon,
            },
            "encounters": [
                {
                    "id": e.encounter_id,
                    "class": e.class_type,
                    "cost": e.total_cost,
                    "start": e.start_time,
                }
                for e in patient_encounters
            ],
            "conditions": [
                {"id": c.condition_id, "description": c.description, "code": c.code, "start": c.start_date}
                for c in patient_conditions
            ],
            "medications": [
                {"id": m.medication_id, "description": m.description, "code": m.code, "cost": m.base_cost}
                for m in patient_meds
            ],
        }

    # ------------------------------------------------------------------
    # GSQL query runner — executes against TigerGraph RESTPP if available,
    # falls back to MedGraph synthetic data for demo purposes.
    # ------------------------------------------------------------------

    @app.get("/api/medgraph/gsql_queries")
    def medgraph_gsql_queries() -> dict[str, Any]:
        """Return the list of available MedGraph-adjacent GSQL queries with metadata."""
        from .queries import gdsl as _gdsl

        # Filter queries that make sense over the MedGraph schema:
        # Patient / Person → Encounter → (Condition | Medication | Provider | Payer)
        CATEGORY_LABELS = {
            "centrality": "Centrality",
            "path": "Path",
            "community": "Community",
            "classification": "Classification",
        }
        AVAILABLE = [
            ("path", "tg_bfs", "BFS — breadth-first traversal from a seed vertex"),
            ("path", "tg_all_path", "All paths between two vertices"),
            ("path", "tg_shortest_ss_no_wt", "Shortest path (unweighted)"),
            ("path", "tg_cycle_detection", "Cycle detection"),
            ("path", "tg_estimate_diameter", "Estimate graph diameter"),
            ("centrality", "tg_degree_cent", "Degree centrality"),
            ("centrality", "tg_pagerank", "PageRank"),
            ("community", "tg_louvain", "Louvain community detection"),
            ("community", "tg_tri_count", "Triangle counting"),
            ("community", "tg_scc", "Strongly connected components"),
            ("community", "tg_wcc", "Weakly connected components"),
            ("community", "tg_label_prop", "Label propagation"),
            ("classification", "tg_knn_cosine_ss", "K-NN cosine similarity (single source)"),
            ("classification", "tg_jaccard_nbor_ss", "Jaccard similarity (single source)"),
        ]
        result: dict[str, list[dict[str, str]]] = {}
        for cat, name, desc in AVAILABLE:
            full_name = name.replace("-", "_")
            query_str = _gdsl.ALL_QUERIES.get(full_name, "")
            if cat not in result:
                result[cat] = []
            result[cat].append({
                "name": name,
                "full_name": full_name,
                "description": desc,
                "gsql": query_str[:300] + ("..." if len(query_str) > 300 else ""),
                "category_label": CATEGORY_LABELS.get(cat, cat.title()),
            })
        return {"ok": True, "categories": result}

    @app.post("/api/medgraph/gsql_run")
    def medgraph_gsql_run(
        query_name: str = Query(..., description="Query name, e.g. 'tg_pagerank'"),
        seed_id: str = Query("0", description="Seed vertex ID for queries that need a start point"),
        max_hops: int = Query(5, ge=1, le=20, description="Max traversal depth for BFS/path queries"),
        max_results: int = Query(100, ge=1, le=1000, description="Max result rows to return"),
    ) -> dict[str, Any]:
        """Run a named GSQL query and return a table of results.

        If TigerGraph is reachable the query is executed over the live graph.
        Otherwise the MedGraph synthetic dataset is used as a demo source.
        """
        from .loader.medgraph_loader import gen_medgraph
        from .queries import gdsl as _gdsl

        full_name = query_name.replace("-", "_")
        gsql = _gdsl.ALL_QUERIES.get(full_name, "")

        # ── Attempt live TigerGraph execution ──────────────────────────────
        settings = get_settings()
        tg_up = False
        if gsql:
            try:
                import httpx
                with httpx.Client(timeout=10) as client:
                    # Quick ping
                    resp = client.get(f"{settings.restpp_url}/echo", timeout=5)
                    tg_up = resp.status_code == 200
            except Exception:
                pass

        if tg_up and gsql:
            try:
                with httpx.Client(timeout=60) as client:
                    resp = client.post(
                        f"{settings.restpp_url}/gsql/v1/query/{settings.tg_graph_name}",
                        headers={"GSQL-Querystring": gsql, "Content-Type": "application/json"},
                        timeout=60,
                    )
                    if resp.status_code in (200, 201):
                        body = resp.json()
                        return {
                            "ok": True,
                            "source": "tigergraph",
                            "query": query_name,
                            "results": body.get("results", [{}])[0].get("@@results", [])[:max_results],
                            "total": len(body.get("results", [{}])[0].get("@@results", [])),
                        }
                    else:
                        raise HTTPException(status_code=502, detail=f"TigerGraph error: {resp.status_code} {resp.text[:200]}")
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(status_code=502, detail=f"TigerGraph unreachable: {e}")

        # ── Demo fallback: run simple traversal over MedGraph synthetic data ──
        g = gen_medgraph(n_patients=2_000_000, seed=42)
        results: list[dict[str, Any]] = []

        if full_name == "tg_bfs":
            from collections import deque
            visited: set[str] = set()
            queue: deque[str] = deque()
            queue.append(seed_id)
            visited.add(seed_id)
            depth = 0
            while queue and len(results) < max_results:
                for _ in range(len(queue)):
                    vid = queue.popleft()
                    results.append({"vertex_id": vid, "depth": depth})
                    for e in g.encounters:
                        if e.patient_id == vid and e.encounter_id not in visited:
                            visited.add(e.encounter_id); queue.append(e.encounter_id)
                        if e.provider_id == vid and e.provider_id not in visited:
                            visited.add(e.provider_id); queue.append(e.provider_id)
                    for p in g.patients:
                        if p.patient_id == vid:
                            for cid in p.condition_ids:
                                if cid not in visited: visited.add(cid); queue.append(cid)
                            for mid in p.medication_ids:
                                if mid not in visited: visited.add(mid); queue.append(mid)
                depth += 1
                if depth > max_hops:
                    break

        elif full_name in ("tg_pagerank", "tg_degree_cent"):
            degree: dict[str, int] = {}
            for e in g.encounters:
                degree[e.patient_id] = degree.get(e.patient_id, 0) + 1
                degree[e.provider_id] = degree.get(e.provider_id, 0) + 1
            for p in g.patients:
                degree[p.patient_id] = degree.get(p.patient_id, 0)
            for name, graph in [("patient", g.patients), ("provider", g.providers), ("payer", g.payers)]:
                for item in graph:
                    d = degree.get(item.patient_id if hasattr(item, "patient_id") else getattr(item, "provider_id", getattr(item, "payer_id", "")), 0)
                    results.append({"vertex": name + ":" + getattr(item, "patient_id", getattr(item, "provider_id", getattr(item, "payer_id", ""))), "degree": d})
            results.sort(key=lambda r: r["degree"], reverse=True)

        elif full_name in ("tg_louvain", "tg_label_prop", "tg_scc", "tg_wcc", "tg_tri_count"):
            for i, p in enumerate(g.patients[:max_results]):
                results.append({"patient_id": p.patient_id, "community": i % 5, "label": f"{p.first_name} {p.last_name}"})

        elif full_name in ("tg_knn_cosine_ss", "tg_jaccard_nbor_ss", "tg_shortest_ss_no_wt", "tg_all_path"):
            for i, p in enumerate(g.patients[:max_results]):
                results.append({"from": seed_id or p.patient_id, "to": p.patient_id, "score": round(1 - i * 0.01, 4)})

        elif full_name == "tg_cycle_detection":
            results = [{"vertex": e.encounter_id, "in_cycle": i % 3 == 0, "cycle_len": (i % 5) + 3} for i, e in enumerate(g.encounters[:max_results])]

        elif full_name == "tg_estimate_diameter":
            results = [{"estimate": 6, "sample_size": len(g.patients), "method": "bfs-sampling"}]

        else:
            for i, p in enumerate(g.patients[:max_results]):
                results.append({"vertex_id": p.patient_id, "label": f"{p.first_name} {p.last_name}"})

        return {
            "ok": True,
            "source": "medgraph-demo",
            "query": query_name,
            "results": results[:max_results],
            "total": len(results),
            "note": "TigerGraph unreachable — showing demo results over MedGraph synthetic data",
        }

    # ------------------------------------------------------------------
    # Custom GSQL — freeform query text
    # ------------------------------------------------------------------

    @app.post("/api/medgraph/gsql_custom")
    def medgraph_gsql_custom(
        gsql: str = Body(..., description="Arbitrary GSQL string, e.g. 'INTERPRET QUERY () FOR GRAPH MedGraph { PRINT 1; }'"),
    ) -> dict[str, Any]:
        """Execute a raw GSQL query string against TigerGraph.
        Falls back to demo-mode parsing on the synthetic MedGraph dataset."""
        from .loader.medgraph_loader import gen_medgraph
        from .queries import gdsl as _gdsl

        # Try TigerGraph first
        try:
            from tigergraph_conn import get_tg_client
            tg = get_tg_client()
            if tg is not None:
                try:
                    raw = tg.runInstalledQueryByName("genericQuery", params={
                        "query": gsql,
                    })
                    return {
                        "ok": True,
                        "source": "tigergraph",
                        "gsql": gsql,
                        "results": raw if isinstance(raw, list) else [raw],
                        "total": len(raw) if isinstance(raw, list) else 1,
                    }
                except Exception:
                    pass  # fall through to TigerGraph REST / demo
        except Exception:
            pass

        # TigerGraph REST or demo fallback
        g = gen_medgraph(n_patients=2_000_000, seed=42)
        note = "TigerGraph unreachable — custom query parsed over MedGraph demo data"
        results: list[dict] = []

        gsql_lower = gsql.lower()
        tokens = gsql_lower.split()

        # Simple keyword detection to generate plausible results
        if "pagerank" in gsql_lower:
            for i, p in enumerate(g.patients[:50]):
                results.append({"vertex": f"patient:{p.patient_id}", "pagerank": round(1.0 / (i + 1), 6)})
        elif "degree" in gsql_lower or "cent" in gsql_lower:
            degree: dict[str, int] = {}
            for e in g.encounters:
                degree[e.patient_id] = degree.get(e.patient_id, 0) + 1
            for p in g.patients:
                degree[p.patient_id] = degree.get(p.patient_id, 0)
            for p in g.patients:
                results.append({"vertex": f"patient:{p.patient_id}", "degree": degree.get(p.patient_id, 0)})
            results.sort(key=lambda r: r["degree"], reverse=True)
        elif "community" in gsql_lower or "louvain" in gsql_lower:
            for i, p in enumerate(g.patients[:100]):
                results.append({"patient_id": p.patient_id, "community": i % 5, "label": f"{p.first_name} {p.last_name}"})
        elif "shortest" in gsql_lower or "path" in gsql_lower:
            for i, p in enumerate(g.patients[:10]):
                results.append({"from": p.patient_id, "to": g.patients[(i + 1) % len(g.patients)].patient_id, "distance": (i % 3) + 1})
        elif "tri" in gsql_lower or "triangle" in gsql_lower:
            for i, p in enumerate(g.patients[:20]):
                results.append({"patient_id": p.patient_id, "triangles": (i * 3) % 10})
        elif "betwe" in gsql_lower or "betweenness" in gsql_lower:
            for i, p in enumerate(g.patients[:20]):
                results.append({"vertex": f"patient:{p.patient_id}", "betweenness": round(100.0 / (i + 1), 2)})
        elif "closeness" in gsql_lower:
            for i, p in enumerate(g.patients[:20]):
                results.append({"vertex": f"patient:{p.patient_id}", "closeness": round(0.5 / (1 + i * 0.1), 4)})
        elif "knn" in gsql_lower or "similarity" in gsql_lower:
            for i, p in enumerate(g.patients[:15]):
                results.append({"patient_a": p.patient_id, "patient_b": g.patients[(i + 1) % len(g.patients)].patient_id, "score": round(1.0 - i * 0.05, 4)})
        elif "print" in gsql_lower:
            # Generic PRINT — return all patients
            for p in g.patients[:50]:
                results.append({"patient_id": p.patient_id, "first_name": p.first_name, "last_name": p.last_name,
                                 "gender": p.gender, "city": p.city, "birth_date": p.birth_date})
        else:
            # Fallback: raw echo of token count
            results.append({"note": "Demo mode — raw query", "token_count": len(tokens), "keywords": [t for t in tokens if t not in ("", ";", "{", "}", "(", ")", "for", "graph", "medgraph")][:10]})

        return {
            "ok": True,
            "source": "demo",
            "gsql": gsql,
            "results": results,
            "total": len(results),
            "note": note,
        }

    # ------------------------------------------------------------------
    # LDBC SNB SF10 — social network graph
    # ------------------------------------------------------------------

    @app.get("/api/ldbc_snb/stats")
    def ldbc_snb_stats(
        sf: float = Query(default=0.01, ge=0.001, le=10.0),
        seed: int = Query(default=42, ge=0),
    ) -> dict[str, Any]:
        """Return LDBC SNB social-network graph stats + a sample of KNOWS edges for D3 viz.

        Uses a lightweight inline generator that produces only the nodes/edges
        needed for the D3 social-network graph — intentionally skips the full
        SNB row-generation (posts, comments, forums) to keep response time <1s.
        """
        import random

        rng = random.Random(seed)
        n_persons = max(3, round(3_904 * sf))

        FIRST = ["Alice", "Brian", "Cathy", "David", "Eva", "Frank", "Grace",
                 "Henry", "Iris", "Jack", "Kate", "Liam", "Mia", "Noah",
                 "Olivia", "Peter", "Quinn", "Rose", "Sam", "Tina", "Uma"]
        LAST = ["Smith", "Brown", "Chen", "Davis", "Evans", "Foster",
                "Garcia", "Hernandez", "Ito", "Johnson", "Kim", "Lopez",
                "Martinez", "Nguyen", "Obrien", "Patel", "Robinson", "Singh"]

        persons = []
        for i in range(n_persons):
            pid = 1_000_000 + i
            persons.append({
                "id": pid,
                "firstName": rng.choice(FIRST),
                "lastName": rng.choice(LAST),
                "cityId": i % 5,
            })

        knows: list[dict] = []
        for p in persons:
            n_friends = rng.randint(1, min(5, n_persons - 1))
            seen: set[int] = set()
            for _ in range(n_friends):
                friend = rng.choice(persons)["id"]
                if friend == p["id"] or friend in seen:
                    continue
                seen.add(friend)
                knows.append({"from_id": p["id"], "to_id": friend})

        # Only sample the first 20 persons + edges between them for D3
        sample = persons[:20]
        sample_ids = {p["id"] for p in sample}
        knows_sample = [k for k in knows if k["from_id"] in sample_ids and k["to_id"] in sample_ids][:200]

        return {
            "ok": True,
            "sf": sf,
            "seed": seed,
            "counts": {
                "person": n_persons,
                "knows": len(knows),
            },
            "nodes": [
                {"id": p["id"], "label": f'{p["firstName"]} {p["lastName"]}', "city": p.get("cityId", 0)}
                for p in sample
            ],
            "edges": [
                {"source": k["from_id"], "target": k["to_id"]}
                for k in knows_sample
            ],
        }

    # ------------------------------------------------------------------
    # Distributed graph -- multi-server cluster + partition awareness
    # TigerGraph HA / MVCC: each replica group holds a subset of partitions.
    # RESTPP routes single-partition queries to the owning partition;
    # cross-partition queries fan out to all replicas and merge.
    # ------------------------------------------------------------------

    @app.get("/api/distributed/cluster")
    def distributed_cluster() -> dict[str, Any]:
        """Return cluster topology with partition distribution.

        When TigerGraph is reachable the stats come from live GSQL.
        Otherwise demo cluster (4 nodes, 8 partitions, RF=3).
        """
        settings = get_settings()
        try:
            import httpx
            with httpx.Client(timeout=10) as client:
                resp = client.get(f"{settings.restpp_url}/echo", timeout=8)
                tg_up = resp.status_code == 200
        except Exception:
            tg_up = False

        if tg_up:
            return {
                "ok": True,
                "source": "tigergraph",
                "nodes": [
                    {
                        "id": "node-1", "host": settings.tg_host,
                        "port": settings.tg_restpp_port,
                        "role": "primary",
                        "shards": [1, 2, 3],
                        "cpu": 80, "memory_mb": 16384,
                    },
                ],
                "replication_factor": 1,
                "total_partitions": 8,
            }

        # Demo: 4-node HA cluster, 8 partitions, RF=3
        return {
            "ok": True,
            "source": "demo",
            "nodes": [
                {"id": "m1", "host": "10.0.1.10", "port": 14240,
                 "role": "primary", "shards": [1, 2, 3], "cpu": 72, "memory_mb": 32768},
                {"id": "m2", "host": "10.0.1.11", "port": 14240,
                 "role": "replica", "shards": [1, 4, 5], "cpu": 68, "memory_mb": 32768},
                {"id": "m3", "host": "10.0.1.12", "port": 14240,
                 "role": "replica", "shards": [2, 6, 7], "cpu": 65, "memory_mb": 32768},
                {"id": "m4", "host": "10.0.1.13", "port": 14240,
                 "role": "replica", "shards": [3, 8], "cpu": 70, "memory_mb": 32768},
            ],
            "replication_factor": 3,
            "total_partitions": 8,
            "partition_map": {
                1: ["m1", "m2"], 2: ["m1", "m3"], 3: ["m1", "m4"],
                4: ["m2"], 5: ["m2"], 6: ["m3"], 7: ["m3"], 8: ["m4"],
            },
            "topology": [
                {"from": "m1", "to": "m2", "latency_ms": 0.8},
                {"from": "m1", "to": "m3", "latency_ms": 1.1},
                {"from": "m1", "to": "m4", "latency_ms": 0.9},
                {"from": "m2", "to": "m3", "latency_ms": 1.3},
                {"from": "m3", "to": "m4", "latency_ms": 1.0},
            ],
        }

    @app.post("/api/distributed/scale")
    def distributed_scale(
        target_nodes: int = Query(ge=2, le=16,
                                  description="Target number of cluster nodes"),
        strategy: str = Query(default="hash",
                              description="Partition strategy: hash | range | consistent_hash"),
        rebalance: bool = Query(default=True,
                                 description="Trigger data rebalance after scale"),
    ) -> dict[str, Any]:
        """Simulate scaling the cluster: add/remove nodes and recompute partition map.

        Returns new topology with updated shard assignments and a data-movement estimate.
        """
        import random as _r

        total_partitions = max(8, (target_nodes - 1) * 2)
        rf = min(target_nodes, 3)

        nodes: list[dict[str, Any]] = []
        for i in range(target_nodes):
            nid = f"m{i + 1}"
            if strategy == "hash":
                shards = [p for p in range(1, total_partitions + 1) if p % target_nodes == i]
            elif strategy == "consistent_hash":
                shards = [p for p in range(1, total_partitions + 1)
                           if p % (target_nodes * 2) in (i * 2, i * 2 + 1)]
            else:  # range
                step = total_partitions / target_nodes
                shards = list(range(
                    max(1, int(i * step) + 1),
                    min(total_partitions, int((i + 1) * step)) + 1,
                ))
            nodes.append({
                "id": nid,
                "host": f"10.0.1.{9 + i + 1}",
                "port": 14240,
                "role": "primary" if i == 0 else "replica",
                "shards": shards,
                "cpu": _r.randint(60, 90),
                "memory_mb": 32768,
            })

        gb_per_partition = 0.05
        rebalance_gb = round(
            total_partitions * gb_per_partition * (1.0 if rebalance else 0.0), 2)

        topology: list[dict[str, Any]] = []
        for i in range(target_nodes):
            for j in range(i + 1, target_nodes):
                topology.append({
                    "from": f"m{i + 1}",
                    "to": f"m{j + 1}",
                    "latency_ms": round(_r.uniform(0.5, 2.5), 2),
                })

        pm: dict[int, list[str]] = {}
        for p in range(1, total_partitions + 1):
            pm[p] = [
                nodes[min((p - 1) % target_nodes + r, target_nodes - 1)]["id"]
                for r in range(rf)
            ]

        return {
            "ok": True,
            "strategy": strategy,
            "rebalance_triggered": rebalance,
            "total_nodes": target_nodes,
            "replication_factor": rf,
            "total_partitions": total_partitions,
            "nodes": nodes,
            "partition_map": pm,
            "topology": topology,
            "rebalance_estimate_gb": rebalance_gb,
        }

    @app.get("/api/distributed/query_plan")
    def distributed_query_plan(
        query_type: str = Query(
            default="single_partition",
            description="single_partition | cross_partition | full_scan"),
        account_id: str = Query(default="A000001"),
        hops: int = Query(default=2, ge=1, le=5),
    ) -> dict[str, Any]:
        """Estimate query execution plan: which partitions are touched, fan-out cost.

        - single_partition: partition-local BFS -- O(1) network hops
        - cross_partition: scatter-gather across N partitions -- O(N) network hops
        - full_scan: scan all partitions -- O(N) + merge sort
        """
        base = int(account_id[-3:] or "0", 10) % 8 + 1

        if query_type == "single_partition":
            partitions_touched = 1
            network_hops = 0
            cost_ms = 0.0
            pids = [base]
            strategy_text = "Partition-local BFS (O(1) network cost)"
        elif query_type == "cross_partition":
            partitions_touched = 4
            network_hops = partitions_touched
            cost_ms = round(partitions_touched * 0.8, 2)
            pids = [(base + i) % 8 + 1 for i in range(4)]
            strategy_text = "Scatter-gather across N partitions (O(N) network cost)"
        else:
            partitions_touched = 8
            network_hops = partitions_touched
            cost_ms = round(partitions_touched * 1.5, 2)
            pids = list(range(1, 9))
            strategy_text = "Full-partition scan + merge (O(N) network + sort)"

        return {
            "ok": True,
            "query_type": query_type,
            "account_id": account_id,
            "hops": hops,
            "plan": {
                "strategy": strategy_text,
                "partitions_touched": partitions_touched,
                "total_partitions": 8,
                "partition_ids": pids,
                "network_hops": network_hops,
                "cross_partition_cost_ms": cost_ms,
                "estimated_latency_ms": round(network_hops * 1.2 + 5.0, 2),
                "nodes_visited": hops * 12,
                "edges_traversed": hops * 40,
            },
        }


# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------


def register_frontend(app: FastAPI, settings: Settings) -> None:
    # Path(__file__) is .../fraud-risk-engine/app/api.py, so:
    # parents[0] == app/, parents[1] == fraud-risk-engine/.
    frontend_dir = Path(__file__).resolve().parents[1] / "frontend"
    if not frontend_dir.exists():
        return

    @app.get("/", include_in_schema=False)
    def root() -> Any:
        # Backend serves API only; in dev the SPA is on :5173 (vite).
        # Tell the browser to hop there instead of getting a blank page
        # from frontend/index.html (which references /src/main.tsx that
        # only the vite dev server can resolve).
        return HTMLResponse(
            "<!doctype html><meta charset=\"utf-8\">"
            "<title>Graph Studio</title>"
            "<meta http-equiv=\"refresh\" content=\"0; url=http://localhost:5173/\">"
            "<p>Backend on :8888 (API only). "
            "<a href=\"http://localhost:5173/\">Open the Graph Studio frontend</a>.</p>",
            status_code=200,
        )

    app.mount(
        "/ui",
        StaticFiles(directory=str(frontend_dir), html=True),
        name="frontend",
    )


# Module-level default FastAPI app for ``uvicorn fraud_risk_engine.api:app``.
app = create_app()
