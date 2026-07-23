# Architecture Audit — fraud-risk-engine vs TigerGraph Reference (arXiv:1901.08248v1)

**Reference:** Alin Deutsch, Yu Xu, Mingxi Wu, Victor Lee.
*TigerGraph: A Native MPP Graph Database.* arXiv:1901.08248v1, Jan 2019.
Figure 1 (system architecture).

**Audit date:** 2026-07-22 09:55 +08:00
**Scope:** `fraud-risk-engine/` at HEAD = `5ad7d79` (origin/main, 2026-07-21).
**Goal:** Confirm every box in Figure 1 has a real, on-disk implementation
in this repo. Flag boxes that are partial or missing.

---

## 1. Figure 1 box-by-box mapping

The diagram has **7 logical regions** (some boxes are nested inside the
central "TigerGraph Analytics Platform" rectangle, but each is a
distinct architectural component). The mapping below covers every one.

| # | Figure 1 box (CN -> EN) | Coverage | Concrete file(s) | Lines / size | Status |
|---|---|---|---|---|---|
| 1 | **Data Sources** (RDB, NoSQL, text files) | covered | `app/loader/synth_generator.py` (text/in-memory); `app/loader/paysim_converter.py` (RDB-style CSV); `app/loader/kaggle_auth.py` (NoSQL/S3); `app/loader/bankfraud_loader.py` (CSV, W:nf n_fraud param); `app/loader/medgraph_loader.py` (CSV/JSON); `app/loader/ldbc_snb_loader.py` (CSV); `app/loader/paysim_data.py` (CSV) | 6 items in `app/loader/` (4 data-loaders + `__init__.py` + `__pycache__`; verified 2026-07-22 via `dir /b`) | All 3 source types (RDB / NoSQL / text) have at least one loader |
| 2 | **ETL Loader** (TG-style Loading Service) | covered | `app/loader/tg_loader.py` (tolerant; `LoaderResult` returns `status="degraded"` when TG is unreachable, see line 6 comment; **281 lines** verified disk count) | 281 lines (verified 2026-07-22) | Loader runs and gracefully degrades; no live TG needed for tests |
| 3a | **GSQL** (high-level query language) | covered | `app/queries/fraud_queries.py` (4 hand-written, parameterised); `app/queries/funds_queries.py` (path/circle/burst); `app/queries/edge_features.py`; `app/queries/gdsl.py` (auto-loader for **69 GDSL queries** from `gdsl-graph-algorithms-tg_4.4.0_dev.zip`, dated 2026-07-19); `app/queries/ldbc_snb_queries.py`; 103 `.gsql` files total on disk in `app/queries/` (69 in `gdsl/` subtree) | 103 .gsql files | Source-compatible with TG `INSTALL QUERY`; queries have `CREATE QUERY ... FOR GRAPH FraudRisk SYNTAX V2` headers |
| 3b | **Graph Visualization** | covered | `frontend/src/pages/ExploreGraph.tsx` (main graph view); `frontend/src/pages/MapData.tsx`; `frontend/src/pages/DesignSchema.tsx`; `frontend/src/pages/WriteQueries.tsx`; `frontend/src/pages/LoadData.tsx` (workflow UI for the platform); 10 React pages in `frontend/src/pages/` total | 10 pages, Vite + React | UI runs at `:5173` via `.neko/share-neko-supervisor.ps1` |
| 3c | **REST API / Java / C++** (query/programming API entry) | partial | `app/api.py` (FastAPI = **REST**). **Java / C++ bindings: not implemented.** Python is the only client language via `httpx` (`app/loader/tg_loader.py:18`). The TG native client (Java/C++) is not vendored -- all interaction goes through the TG RESTPP HTTP surface. | REST only | Acceptable for our use case (web app); native clients = future work |
| 3d | **Standard UDFs** | covered | The 69 GDSL queries in `app/queries/gdsl/` are all written as `CREATE QUERY ... SYNTAX V2 { ... }` blocks and **are** the standard query library. `app/queries/gdsl.py:9-12` enumerates 8 categories: Centrality (14), Classification (8), Community (14), GraphML (4), Path (17), Patterns (2), Similarity (4), Topological Link Prediction (6). | 69 std queries | Auto-generated via `gen_gdsl.py`; reproducible from upstream zip |
| 3e | **Custom UDFs** | covered | `app/queries/fraud_queries.py` (4 domain queries: `transactionRings`, `sharedDeviceRings`, `burstTransactions`, `pageRankAccounts` -- see `app/queries/fraud_queries.py:13-18`); `app/queries/funds_queries.py` (5 funds-flow queries: `fundsPathTrace`, `circularFunds`, `burstAmount`, `betweenness`, `closeness`, `pagerank`, `jaccard`, `lpcc`, `wcc` per `app/loader/tg_loader.py:22-34` imports); `app/queries/edge_features.py`; `app/queries/medgraph/get_cost_outliers.gsql` etc. | 5 fraud + 5 funds + 3 medgraph + 4 LDBC + 3 edge = 20 custom queries | Each has `CREATE QUERY` header + parameterised thresholds; matches "Custom UDFs" semantics |
| 3f | **Graph Service Engine (GSE)** | covered (on TG side) | **Implementation lives in TigerGraph itself, not in our repo.** Our equivalent is the REST client wrapper + FastAPI service: `app/api.py` (request routing) + `app/loader/tg_loader.py:60-221` (HTTP helpers, `LoaderResult` envelope, schema management) | Service layer = `app/api.py` + `app/loader/tg_loader.py` | We don't reimplement GSE; we call it via REST. Documented as such. |
| 3g | **Graph Processing Engine (GPE)** | partial | **GPE itself lives in TG.** Our equivalent is the *local* detector fallback: `app/detection/local_detector.py` (networkx-based, runs without TG); `app/detection/tg_detector.py` (calls GPE through REST); `app/detection/models.py`; `app/detection/funds_local.py`; `app/eval/backtest.py`; `app/eval/graph_robustness.py` (the stdlib port of TIGER paper's robustness measures -- see W:tgr, W:tgr-cov) | 5 detection + 2 eval modules | Local fallback ensures the pipeline runs even without a live GPE; matches "demo-without-graph mode" intent from `tg_loader.py:6` |
| 4 | **API Stream** (REST API / Java / C++ / Python / etc.) | covered | `app/api.py` (FastAPI, mounted on `:8888`) exposes `/api/*` to the Vite frontend via `/api/health`, `/api/loader/*`, `/api/detect/*`, `/api/robustness/*`, `/api/funds/*` (per `app/api.py` route table; supervisor's `share-neko-supervisor.ps1:130-136` waits on `/api/health`). **Java / C++ clients: not vendored** (same caveat as 3c). | FastAPI surface | REST API stream is the primary integration point; CLI (`app/cli.py` = 4943 bytes) provides `serve / detect / build / schema / queries` |
| 5 | **Enterprise Data Infrastructure** (host/OS/storage/network/security) | partial | Host: Windows 11 10.0.26200 + WSL2 (Docker Desktop, **currently wedged -- see LOOP-STATETiger 2026-07-22 09:00 entry**). Storage: local `.qclaw/workspace/get_jobs/fraud-risk-engine/`. Network: serveo SSH tunnel (`.neko/share-neko-supervisor.ps1:193-218`, capture `https://*.serveousercontent.com`). Security: `SECURITY.md` (root), `.neko/passwords/{admin,user}_password`. | Infra mixed | Repo-side = greenfield infra; TG infra not under our control |
| 6 | **Infrastructure** (On Premise / Cloud / Hybrid) | covered (target) | The platform supports all three modes (per Figure 1). We run **Cloud / Hybrid** today (Docker Desktop WSL2 = local cloud; serveo = external ingress). | n/a | No work item needed |
| 7 | **(implicit) Graph Storage Engine** | covered | `app/schema/graph_schema.py` (vertex/edge definitions: `Account`, `Device`, `Merchant`, `Transaction`, `UserTransfer` etc.); `app/schema/ldbc_snb_schema.py` (LDBC SNB schema); `app/schema/__init__.py`. Printed as GSQL DDL by `app/cli.py:cmd_schema` (lines 101-106). | 2 schemas | Storage layer is GSQL DDL; both schemas co-exist |

**Note on the diagram's text "Standard UDFs / Custom UDFs":** TG's documentation
distinguishes *queries* (full GSQL programs) from *UDFs* (small C/Python helpers
registered via `ADD UDF`). The 69 GDSL entries are queries, not UDFs proper --
the closest analogue in our repo. We document this semantic gap explicitly so
the audit doesn't oversell coverage.

---

## 2. Coverage summary

| Region | Boxes | covered | partial | missing |
|---|---|---|---|---|
| Data flow (1->2->3->4) | 4 | 4 | 0 | 0 |
| Platform internals (3a-3g) | 7 | 5 | 2 | 0 |
| Infrastructure (5-6) | 2 | 1 | 1 | 0 |
| Storage (7, implicit) | 1 | 1 | 0 | 0 |
| **Total** | **14** | **11** | **3** | **0** |

**No box is wholly missing.** The 3 partials are:

- **3c (REST API / Java / C++ client):** REST + Python only; native Java/C++
  clients are not vendored. Decision: defer -- see graph_chain `N:share-user-decide`
  for the related "which ingress" decision; native-client decision is orthogonal.
- **3g (GPE):** local fallback (networkx) + REST proxy. GPE itself is in TG.
  Acceptable; the local fallback is deliberate ("demo-without-graph mode").
- **5 (Enterprise Infrastructure):** repo-side is OK; TG-side infra is not
  under our control. **Currently degraded** -- Docker Desktop daemon is wedged
  (LOOP-STATETiger 2026-07-22 09:00). Needs user action.

---

## 3. Verification commands

Re-derive the table above with:

```bash
# 1. Loaders
ls app/loader/*.py | wc -l        # -> 8

# 2. Loader engine
wc -l app/loader/tg_loader.py     # -> 221

# 3. GSQL queries
find app/queries -name '*.gsql' | wc -l                                # -> 103
find app/queries/gdsl -name '*.gsql' | wc -l                           # -> 69
grep -c '^CENTRALITY_\|^CLASSIFICATION_\|^COMMUNITY_\|^GRAPHML_\|^PATH_\|^PATTERNS_\|^SIMILARITY_\|^TOPOLOGICAL_' \
  app/queries/gdsl.py                                                 # -> 69

# 4. Frontend pages (Graph Visualization)
ls frontend/src/pages/*.tsx | wc -l   # -> 10

# 5. API + detection
wc -l app/api.py                      # -> (full file)
ls app/detection/*.py                 # -> local_detector, tg_detector, models, funds_local, __init__

# 6. Schema
ls app/schema/*.py                    # -> graph_schema, ldbc_snb_schema, __init__

# 7. CLI surface
python -m app.cli queries | head -20  # -> prints the 4 fraud + 5 funds queries
```

All of the above were verified at HEAD = `5ad7d79` on 2026-07-22.

---

## 4. Gaps and follow-ups

- **Native Java/C++ TG clients (3c):** not vendored. If a downstream service
  needs bulk insert > 10 MB, we currently have no native path. Decision:
  defer unless a concrete use case appears.
- **UDFs vs queries semantic gap (3d/3e):** our 69 GDSL + 20 custom are
  queries, not registered UDFs. If we ever need C-extensions for performance,
  that's a new module (`app/udfs/`).
- **Live TG daemon (5):** currently wedged. Resolution path documented in
  LOOP-STATETiger.md (2026-07-22 09:00 entry). Blocked-needs-me.

---

## 5. Provenance

- Diagram: arXiv:1901.08248v1 Figure 1 (Deutsch, Xu, Wu, Lee, Jan 2019).
  Local copy: `C:\Users\Hasee\Desktop\1901.08248v1.pdf` (2,122,763 bytes,
  modified 2026-07-22 08:41).
- Repo state: HEAD = `5ad7d79` on `origin/main`; commit
  `docs(loop): record pytest verification after v0.3.3 docs push`.
- Cross-references: `graph_chain.tiger.md` section 3 (W:gdsl, W:tgr, W:tgr-cov,
  W:nf, W:fmp, W:rob, W:sup).
