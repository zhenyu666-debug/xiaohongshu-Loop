# fraud-risk-engine

TigerGraph-backed **financial fraud risk detection engine** with a
**Multi-view + Dashboard + Investigation** visualization stack and a
**dual-layer markdown memory**.

> Status: v0.3.1 — TIGER robustness surface (AlertKind + `/api/robustness`) wired through the React frontend (**Graph Robustness** tab). 121/121 tests passing.

---

## Why this exists

Most "fraud detection" demos only show single-account rule flags. This
project models a fraud graph:

- **Vertices.** Customer, Account, Card, Device, IP, Merchant, Transaction.
- **Edges.** `OWNS`, `HAS_CARD`, `USES_DEVICE`, `LOGGED_FROM`, `PAID_TO`,
  `FROM_ACCOUNT`, `TO_ACCOUNT`, `SHARES_DEVICE`, `SHARES_IP`.
- **Detection.**

  1. **transactionRings** — short cycles `A → B → C → A` on the
     `FROM_ACCOUNT`/`TO_ACCOUNT` edges.
  2. **sharedDeviceRings** — accounts sharing ≥ 3 devices or IPs.
  3. **burstTransactions** — accounts with ≥ N outgoing transactions
     inside a sliding window.
  4. **pageRankAccounts** — top-K by out-degree (a coarse centrality
     proxy that stays portable across TigerGraph versions).
  5. **tg_wcc** — Weakly Connected Components (entity-resolution: maps
     accounts in the same fraud-identity cluster).
  6. **tg_lpcc** — Label Propagation Community Detection (finds tightly-knit
     fraud rings without pre-specifying K).
  7. **tg_jaccard** — Jaccard similarity scoring (shared-neighbor /
     union-neighbor ratio for identity-link strength).
  8. **tg_betweenness** — Betweenness centrality (identifies broker / mule
     accounts sitting on many shortest paths).
  9. **tg_closeness** — Closeness centrality (hub accounts well-connected
     to many others).

- **Visualisation.** Three layers (no JS framework, no CDN — works
  air-gapped):

  - **Multi-view** — severity bar chart, kind pie, risk-score dots, full
    bipartite overview with planted rings highlighted.
  - **Dashboard** — KPI cards + per-type vertex/edge counts + alert
    table; click an alert to drill down.
  - **Investigation** — click any alert to render a focus graph of the
    involved accounts plus a chip-list of identities and a JSON
    evidence pane.

---

## Runtime topology

```
   ┌───────────────────────────┐           ┌──────────────────────────────┐
   │  Windows host / FastAPI   │  httpx    │  WSL2 / Docker container     │
   │  (Python 3.10+ stdlib +   │ ────────▶ │  tigergraph/tigergraph:      │
   │   fastapi + pydantic +    │           │   latest, RESTPP on :14240  │
   │   httpx)                  │ ◀──────── │   GSQL on :14240           │
   └───────────────────────────┘           └──────────────────────────────┘
            │                                       ▲
            │  /ui/* static frontend                │
            ▼                                       │
      browser (vanilla CSS+JS)                       │
            ⮕ reads /api/* JSON
```

When TigerGraph is not reachable the API transparently falls back to an
**in-memory** detector that runs the same algorithmic checks against a
synthetic dataset. This is what tests and the frontend hit when the
TigerGraph container is down.

---

## Quick start

```bash
# 1. Make sure Docker Desktop is running and WSL2 backend is enabled.
docker info                # should show Server Version

# 2. Pull & start a TigerGraph container (one-time setup).
docker run -d --name tigergraph \
  -p 14240:14240 \
  tigergraph/tigergraph:latest

# 3. Install the Python package (no fancy deps — works offline).
cd fraud-risk-engine
pip install -e ".[dev]"

# 4. Run the CLI
python -m app.cli doctor         # check Python + httpx versions
python -m app.cli schema         # print the full GSQL schema
python -m app.cli build          # build a synthetic dataset
python -m app.cli detect         # run all 4 detection algorithms
python -m app.cli serve          # launch the FastAPI on :8765

# 5. Open the frontend
#    http://localhost:8765/ui/   (or http://localhost:8765/ui/index.html)
```

If you don't have a TigerGraph container yet, **steps 1-2 are optional** —
the API still serves everything using the in-memory fallback.

---

## API surface

| Endpoint                                  | Method | Description |
|---|---|---|
| `/api/health`                             | GET    | Liveness + TigerGraph reachability |
| `/api/config`                             | GET    | Settings (no secrets) |
| `/api/dataset` (POST)                     | POST   | Build + persist synthetic dataset |
| `/api/dataset` (GET)                      | GET    | Dataset manifest + counts |
| `/api/loader/run` (POST)                  | POST   | Run ping/schema/queries/load stages |
| `/api/detector/run` (POST)                | POST   | Run detector (auto/local/tigergraph) |
| `/api/detector/latest` (GET)              | GET    | Return the latest detection run |
| `/api/memory/static` (GET)                | GET    | Static markdown memory |
| `/api/memory/dynamic` (GET)               | GET    | Dynamic memory (regenerated each run) |
| `/api/robustness` (GET)                   | GET    | TIGER-port `RobustnessReport` (density, avg degree, clustering, diameter, connectivity, assortativity) + surfaced alert |
| `/api/bankfraud/sample` (GET)             | GET    | Kaggle banking-fraud feature matrix (subset) as fraud-aware graph |
| `/api/medgraph/sample` (GET)              | GET    | Synthea MedGraph (synthetic patient health graph) |
| `/api/medgraph/patient/{id}` (GET)        | GET    | Patient detail (encounters + conditions + medications) |
| `/ui/`                                    | GET    | Vanilla HTML/SVG multi-view UI |
| `frontend/` (Vite)                        | dev    | React Graph Studio UI (5 schema/data tabs + PaySim/MedGraph/Robustness visualisations) |

---

## Testing

```bash
pytest -q
# 110 passed
```

The test suite covers:

- generator determinism + planted-ring invariants (test_synth_generator)
- GSQL schema + query strings (test_schema_and_queries)
- detection algorithms + GSQL post-processors (test_detection)
- FastAPI surface via `TestClient` (test_api)
- static + dynamic memory roundtrips (test_memory)
- multi-hop graph traversal: identity + funds flow (test_profile_multihop)
- threshold sweep + HTML report rendering (test_backtest)

---

## Memory layer

- **Static** — `docs/MEMORY-STATIC.md`, checked in, captures long-lived
  decisions (topology, runtime invariants, dependency policy).
- **Dynamic** — `data/output/MEMORY-DYNAMIC.md`, regenerated on every
  detection run, captures the latest snapshot + alerts + next-step
  hints.

Both are exposed through `/api/memory/static` and `/api/memory/dynamic`
and rendered side-by-side in the **Memory** tab of the UI.

---

## Project layout

```
fraud-risk-engine/
├── app/
│   ├── api.py                  # FastAPI surface
│   ├── cli.py                  # python -m app.cli
│   ├── config.py               # Settings (no pydantic-settings)
│   ├── detection/
│   │   ├── local_detector.py   # in-memory detector (no runtime needed)
│   │   ├── tg_detector.py      # TigerGraph detector with graceful fallback
│   │   └── models.py           # RiskAlert, DetectionRun, ...
│   ├── loader/
│   │   ├── synth_generator.py  # deterministic synthetic data
│   │   └── tg_loader.py        # schema install + RESTPP upsert
│   ├── memory/
│   │   ├── static_memory.py
│   │   └── dynamic_memory.py
│   ├── queries/
│   │   └── fraud_queries.py    # 4 GSQL CREATE QUERY definitions
│   └── schema/
│       └── graph_schema.py     # 7 vertex + 9 edge DDL
├── frontend/                   # vanilla HTML/SVG (no CDN)
├── data/
│   └── output/MEMORY-DYNAMIC.md
├── docs/
│   └── MEMORY-STATIC.md
├── tests/                      # pytest -q
├── pyproject.toml
└── README.md
```

---

## License

MIT.
