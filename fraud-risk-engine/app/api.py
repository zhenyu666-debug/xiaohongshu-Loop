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

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
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
from .detection.models import DetectionRun
from .detection.tg_detector import TigerGraphDetector, run_remote_detector
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
        # temporarily mutate settings if user supplied overrides
        s = get_settings()
        kwargs: dict[str, Any] = dict(
            accounts=req.accounts or s.synth_accounts,
            devices=req.devices or s.synth_devices,
            merchants=req.merchants or s.synth_merchants,
            transactions=req.transactions or s.synth_transactions,
            fraud_rings=req.fraud_rings or s.synth_fraud_rings,
            seed=req.seed if req.seed is not None else s.synth_seed,
        )
        ds = build_dataset(**kwargs)
        manifest = _persist_dataset(ds, DATA_SEED_DIR)
        STATE["latest_dataset"] = ds
        return {"ok": True, "manifest": manifest}

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
    # Profile — multi-hop BFS
    # ------------------------------------------------------------------

    @app.get("/api/profile/{account_id}")
    def profile_bfs(
        account_id: str,
        hops_identity: int = 3,
        hops_funds: int = 4,
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
        max_hops: int = 3,
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
    ) -> dict[str, Any]:
        """Serve the real Banking Fraud dataset (from local xlsx cache).

        - sample_size: max graph nodes (default 300)
        - fraud_ratio: fraction of fraud nodes in the sample (default 0.5)
        """
        return bankfraud_build(sample_size=sample_size, fraud_ratio=fraud_ratio)

    # ------------------------------------------------------------------
    # MedGraph — Synthea-style patient health graph
    # ------------------------------------------------------------------

    @app.get("/api/medgraph/sample")
    def medgraph_sample(
        n_patients: int = Query(default=80, ge=1, le=500),
        seed: int = Query(default=42, ge=0),
    ) -> dict[str, Any]:
        """Serve a synthetic Synthea-style patient graph.

        Generates n_patients patients with encounters, conditions, medications,
        providers, and payers — linked in a D3-ready graph format.
        """
        from .loader.medgraph_loader import build_medgraph_response

        return build_medgraph_response(n_patients=n_patients, seed=seed)

    @app.get("/api/medgraph/patient/{patient_id}")
    def medgraph_patient(patient_id: str) -> dict[str, Any]:
        """Return full profile of a single patient: demographics + clinical history."""
        from .loader.medgraph_loader import gen_medgraph

        g = gen_medgraph(n_patients=80, seed=42)
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
        index = frontend_dir / "index.html"
        if index.exists():
            return FileResponse(index)
        return JSONResponse({"detail": "no frontend bundled"}, status_code=404)

    app.mount(
        "/ui",
        StaticFiles(directory=str(frontend_dir), html=True),
        name="frontend",
    )


# Module-level default FastAPI app for ``uvicorn fraud_risk_engine.api:app``.
app = create_app()
