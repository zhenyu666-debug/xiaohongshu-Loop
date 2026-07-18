# CHANGELOG

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
