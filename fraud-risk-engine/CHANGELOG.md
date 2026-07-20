# CHANGELOG

## 0.3.2 — 2026-07-20

### Added

- **Funds-flow detector suite** — three new analysis paths ported from
  the operator-supplied Cypher statements into TigerGraph GSQL:
  - `fundsPathTrace.gsql` — multi-hop smurfing path analysis
    (1..5 hop walk from a seed account, summing the cumulative
    amount along the chain).
  - `circularFunds.gsql` — 3..6 hop circular laundering detection,
    extending the existing 3-hop `transactionRings` query.
  - `burstAmount.gsql` — per-source-account average vs every edge;
    flags transfers that exceed `burst_factor × avg` (default 5×).
- `app/queries/funds_queries.py` — exports the GSQL strings and a
  loader that reads them from `app/queries/funds/*.gsql`.
- `app/queries/__init__.py` — re-exports
  `GSQL_FUNDS_PATH_TRACE`, `GSQL_CIRCULAR_FUNDS`, `GSQL_BURST_AMOUNT`.
- `app/loader/tg_loader.py` — funds queries included in
  `install_queries` so `/api/loader/run` ships them all in one shot.
- `app/detection/funds_local.py` — pure-Python fallbacks for all
  three funds-flow detectors. Mirrors the GSQL semantics against
  `ds.from_account` / `ds.to_account` so the demo-without-graph
  frontend mode and unit tests run without a TigerGraph instance.
- `app/detection/models.py` —
  - `AlertKind.FUNDS_PATH_TRACE`, `AlertKind.CIRCULAR_FUNDS`,
    `AlertKind.BURST_AMOUNT`.
  - Three factory functions:
    `funds_path_trace_alert_from_gsql`,
    `circular_funds_alert_from_gsql`,
    `burst_amount_alert_from_gsql`.
  - All factories guard `None` / empty / wrong-type inputs.
- `app/detection/tg_detector.py` — wires the three new GSQL queries
  into `TigerGraphDetector.run()` with the same `try / except` shape
  as the existing 69 GDSL queries.
- `app/detection/local_detector.py` — wires the local fallbacks into
  `run_local_detector()`. Local threshold lowered to `min_total=1000`
  to match the planted-ring amount distribution in the synthetic
  dataset (production default stays at 50 000 — see API docs).
- `app/api.py` — five new routes:
  - `GET /api/funds/path?start_id=&start_ts=&max_hops=&max_paths=`
  - `GET /api/funds/circles?min_total=&max_hops=&min_hops=`
  - `GET /api/funds/burst?burst_factor=&start_ts=`
  - `POST /api/funds/monitor/start` — kicks off the APScheduler-free
    background monitor with `interval_minutes`, optional `webhook_url`,
    `webhook_token`, and `dry_run` flag.
  - `POST /api/funds/monitor/stop` and `GET /api/funds/monitor`
    for runtime control.
- `app/scheduler/funds_monitor.py` — lightweight, dependency-free
  background-thread job (no APScheduler needed): every `interval_minutes`
  re-runs the three detectors over a freshly-built synthetic dataset
  (or a user-supplied seed), packs the resulting alerts into a single
  webhook payload, and POSTs it to the configured URL. Supports
  bearer-token auth and a `dry_run` mode for offline testing.

### Tests

- `tests/test_funds.py` — 10 tests (3 factory × 3 detectors + 1 e2e).
- `tests/test_funds_monitor.py` — 5 tests covering singleton,
  start/stop lifecycle, factory tolerance, and one-shot pipeline.
- 147/147 green (was 132 → +15).

## 0.3.1 — 2026-07-19

### Added

- `bankfraud_loader` `n_fraud` parameter — explicit absolute count of fraud
  nodes in the sample graph, overrides `fraud_ratio` when supplied (clamped
  to available fraud rows and to `sample_size`). Wired through
  `build_graph`, `build_api_response`, and the `/api/bankfraud/sample` query
  surface (`n_fraud=0..218`).
- `tests/test_bankfraud.py` — 7 unit tests covering ratio contract,
  `n_fraud` override / clamp / zero / negative, and `build_api_response`
  threading.
- `tests/test_api.py` — 4 API tests covering the `n_fraud` query param
  (override, zero, clamp, default).

### Tests

- 132/132 green (was 121 → +11).

## 0.3.0 — 2026-07-19

v0.3.0 extends the algorithm portfolio with graph-theoretic robustness
measures (TIGER port) and a per-account MedGraph view (Synthea-style
patient graph).

### Added

- `app/eval/graph_robustness.py` (TIGER library port, stdlib-only)
  — composite robustness measures: density, average degree, clustering
  coefficient, diameter, edge / node connectivity lower bounds, degree
  assortativity, and a power-iteration spectral-radius estimate.
- `app/queries/edge_features.py` (TigerLily port, stdlib-only) — six
  edge-feature operators: Hadamard, difference, L1, L2, concatenation,
  cosine similarity, plus `apply_operator` dispatch and registry.
- `app/loader/medgraph_loader.py` + `app/queries/medgraph/*` — Synthea
  patient graph: 26 VERTEX + 41 EDGE schema, 6 GSQL queries
  (`get_patient_conditions`, `get_patient_codes`, `get_code_cost`,
  `get_cost_outliers`, `check_distance`, `cosine_patient_demographics`),
  synthetic patient generator with deterministic seed.
- `app/loader/bankfraud_loader.py` — real Kaggle Banking Fraud dataset
  loader (xlsx → API-ready graph dict with fraud/non-fraud nodes).
- `app/queries/gdsl.py` + `app/queries/gdsl/` — TigerGraph Graph
  Algorithm Library v4.4.0_dev port: 69 GSQL queries across Centrality,
  Classification, Community, GraphML, Path, Patterns, Similarity, and
  Topological Link Prediction categories.
- `app/queries/edge_features.py` — TigerLily operator port
  (Hadarmard / L1 / L2 / cosine / concatenation / difference).
- `app/eval/graph_robustness.py` — TIGER `measures` subset port
  (stdlib-only, no networkx).
- `app/detection/models.py::robustness_alert_from_report` — factory
  that converts a `RobustnessReport` into a `RiskAlert`, surfacing
  `graph_robustness_low_connectivity` (edge_connectivity <= 2) and
  `graph_robustness_dense` (density >= 0.30) as outlier signals.
- `GET /api/robustness` — returns the full `RobustnessReport` and the
  surfaced alert for the active dataset, so the Dashboard can render
  the measures table.
- `GET /api/medgraph/sample` and `GET /api/medgraph/patient/{id}` —
  Synthea-style patient graph endpoints.
- `GET /api/bankfraud/sample` — real Kaggle banking-fraud dataset
  endpoint (sample_size, fraud_ratio).

### Changed

- `app/detection/local_detector.py::run_local_detector` — now also
  computes `compute_robustness(ds)` and appends the surfaced
  robustness alert to its alert list.
- `app/detection/tg_detector.py` — wired all 69 GDSL queries through
  TigerGraphDetector.run() with per-query try/except and a centralised
  `detail_parts` accumulator; degraded-fallback path inherits the new
  robustness alert via `run_local_detector`.
- `app/detection/__init__.py` — exports `robustness_alert_from_report`.
- `frontend/index.html` — title reflects all five tabs.

### Tested

```text
pytest -q
121 passed, 1 warning in 13.18s
test_api                  x 12
test_backtest             x 11
test_detection            x 16
test_edge_features        x 13
test_graph_robustness     x 29
test_medgraph             x  7
test_memory               x  4
test_profile_multihop     x 21
test_schema_and_queries   x  4
test_synth_generator      x  4
```

## 0.2.0 — 2026-07-18

v0.2.0 adds evaluation, profiling, and memory to the base v0.1.0 build.

### Added

- `app/eval/backtest.py` — threshold sweep harness (`backtest_run`) over a
  configurable 11-point grid (0.0–1.0). Reports precision/recall/F1 per
  threshold, identifies best-F1 configuration, and renders a self-contained
  HTML report with a results table and summary ring chart.
- `app/profile/graph_search.py` — multi-hop subgraph extraction:
  `bfs_identity` (shared-device/IP networks up to 3 hops) and
  `bfs_funds` (transaction flow up to 4 hops, with directional and merchant
  sink modes). Both are bounded by `max_hops` and `max_nodes`.
- `app/memory/static_memory.py` / `docs/MEMORY-STATIC.md` — static markdown
  memory capturing long-lived architecture decisions, topology invariants,
  and dependency policy.
- `app/memory/dynamic_memory.py` — dynamic markdown memory regenerated on
  every detection run; includes a graph snapshot, alert summary, and
  next-step hints.
- `app/cli.py` — added `fraud-risk-engine` as a console script entry point.
- `start-server.bat` — double-click Windows launcher for the FastAPI server
  (default port 8765, configurable).

### Changed

- `app/api.py` — `/api/profile/{account_id}` multi-hop subgraph endpoint
  with `hops_identity`, `hops_funds`, `funds_direction`, and
  `include_merchants` query parameters.
- `pyproject.toml` — corrected package name from `fraud_risk_engine` to
  `app` to match the source directory; `fraud-risk-engine` CLI script now
  works without sys.path conflicts.
- `frontend/index.html` — title reflects all four tabs: Multi-view,
  Dashboard, Investigation, Memory.
- `frontend/app.js` — Memory tab now calls `/api/memory/static` and
  `/api/memory/dynamic`; Refresh button re-triggers detection.
- `README.md` — updated test count (59), status (v0.2.0), and per-file
  test breakdown.

### Tested

```text
pytest -q
59 passed
test_api         ×  9
test_backtest     × 11
test_detection   ×  6
test_memory      ×  4
test_profile_multihop × 21
test_schema_and_queries ×  4
test_synth_generator   ×  4
```

## 0.1.0 — 2026-07-16

Initial end-to-end build.

### Added

- `app/loader/synth_generator.py` — deterministic, stdlib-only synthetic
  data generator (customers, accounts, cards, devices, IPs, merchants,
  transactions + planted fraud rings + computed `SHARES_DEVICE` /
  `SHARES_IP` edges).
- `app/schema/graph_schema.py` — 7-vertex, 9-edge GSQL schema for the
  `FraudRisk` graph.
- `app/queries/fraud_queries.py` — four detection queries:
  `transactionRings`, `sharedDeviceRings`, `burstTransactions`,
  `pageRankAccounts`. All parameterised.
- `app/loader/tg_loader.py` — RESTPP loaders for schema + queries + bulk
  upload (`upsert_vertices`, `upsert_edges`, `load_dataset`).
- `app/detection/local_detector.py` — backend-equivalent in-memory
  detector (same alert shapes as the GSQL queries).
- `app/detection/tg_detector.py` — TigerGraph detector with graceful
  fallback.
- `app/detection/models.py` — `RiskAlert`, `AlertSeverity`, `AlertKind`,
  `GraphSnapshot`, `DetectionRun` + GSQL post-processors.
- `app/api.py` — FastAPI surface (`/api/health`, `/api/config`,
  `/api/dataset`, `/api/loader/run`, `/api/detector/run`,
  `/api/detector/latest`, `/api/memory/static`, `/api/memory/dynamic`).
- `app/memory/{static,dynamic}_memory.py` — dual-layer markdown memory.
- `frontend/` — vanilla HTML + CSS + JS multi-view, dashboard, and
  investigation views. No CDN, works air-gapped.
- `app/cli.py` — `python -m app.cli doctor|build|detect|serve|schema|queries`.
- `tests/` — 23 pytest cases covering generator, schema, queries,
  detector, API, and memory.

### Notes

- Dependencies limited to `fastapi`, `uvicorn`, `pydantic`, `httpx` and
  the standard library. Optional Streamlit/Plotly stack is in
  `requirements_optional.txt` for users who want it.
- TigerGraph container pulled via `docker run -d --name tigergraph -p
  14240:14240 tigergraph/tigergraph:latest`. The fetch was prepared but
  blocked by the host's docker-mirror policy at integration time; until
  that is resolved the API falls back to the in-memory detector
  transparently (no code changes needed).

### Tested

```text
pytest -q
23 passed
```

## v0.3.0 - 2026-07-19 - GDSL + MedGraph + TigerLily + TIGER + BankFraud/PaySim

### Added
- GDSL import: 69 GSQL queries (Centrality, Classification, Community, GraphML, Path, Patterns, Similarity, TLP) imported from TigerGraph Graph Algorithm Library v4.4.0_dev (commit 9f01f27)
- MedGraph integration: Synthea 26V/41E patient-health graph, 6 GSQL queries, synthetic loader, /api/medgraph/{sample,patient/{id}}, MedGraphView.tsx (commit b5b9d12)
- TigerLily edge-feature operators: stdlib-only port of tigerlily.operator (hadamard/difference/l1/l2/concat/cosine) (commit cb29b61)
- TIGER graph-robustness measures: stdlib-only port of graph_tiger.measures (density, average_degree, clustering_coefficient, diameter_small, edge_connectivity, node_connectivity, degree_assortativity, spectral_radius_estimate) (commit 78f5851)
- BankFraud (Kaggle 138MB xlsx + 500-row JSON cache) loader
- PaySim synthetic generator + CSV converter
- React Graph Studio frontend (Vite + TypeScript): LoadData / ExploreGraph / WriteQueries / MapData / DesignSchema / PaySimView pages

### Changed
- app/loader/medgraph_loader.py: deterministic ID counter (replaces uuid.uuid4)
- app/api.py: /api/medgraph/sample n_patients constraint relaxed (ge=1, le=500)
- app/api.py: /api/paysim/sample fraud_rate explicit Query(float) annotation

### Tests
- 110/110 green (up from 82 at v0.2.0)
- +13 TigerLily tests
- +16 TIGER robustness tests
- +7 MedGraph tests
