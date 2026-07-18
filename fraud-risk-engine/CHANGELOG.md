# CHANGELOG

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
