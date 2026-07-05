# LOOP-STATE.md

Cursor agent's working state for this repo. Read this **first** every run so we never redo finished work.

## Mission
"对GUI把所有的功能放进去 优化一下" — 把 xiaohongshu-saas、donor-screener-pbp、data-lakehouse 三个模块整合到一个 React 控制台里，同时优化 UX/UI、性能、功能完整性。

## Status: ALL 6 MILESTONES DONE (M1-M6, 9 commits)

| ID | milestone | commit |
|----|-----------|--------|
| M1 | Tailwind + shadcn + Router + QueryClient + AppShell layout | (pre-M3 stack commits) |
| M2 | Dashboard / Accounts / Tasks 三页 shadcn + dark mode | (pre-M3 stack commits) |
| M3a | donor-screener-pbp FastAPI + candidates API | 99ff1f5 |
| M3b | xhs upstream gateway + Candidates 3 frontend pages | adf3ea8 |
| M4a | data-lakehouse FastAPI + Trino wrapper + seed fallback | ee6fe0f |
| M4b | Analytics 4 frontend pages | a4aac78 |
| M5b | backend: SSE events + alerts engine + TTL cache | cc6afe0 |
| M5f | frontend: useSSE + useVirtualizedList + AlertsCenter | 7942e54 |
| M6  | docker-compose 3 services + e2e_smoke + README 架构图 | f236749 |

## Test counts
- xhs-saas backend pytest: **39/39**
- xhs-saas console vitest: **21/21**
- pbp-api pytest: **5/5**
- lakehouse-api pytest: **5/5**
- **TOTAL: 70/70**

## What got built

### Frontend console (`xiaohongshu-saas/web/console/`)
12 pages: Dashboard, Accounts, Tasks, CandidatesList (virtualized >200 rows), CandidatesTop20, CandidateDetail, AnalyticsOverview, AnalyticsPvUv, AnalyticsFunnel, AnalyticsTopItems, AlertsCenter (SSE live), Settings.

Custom hooks: useSSE (fetch+ReadableStream SSE parser with 2s reconnect), useVirtualizedList (windowed rows), useDebounce, useInterval, useLocalStorage.

### Backend gateway (`xiaohongshu-saas/app/api/v1_gateway.py`)
HTTP gateway `/api/v1/{short}/{path:path}` forwarding to pbp/lakehouse. `/health/all` aggregates self + upstreams (3s TTL cache). `/cache/clear` + `/cache/stats` admin endpoints.

### Backend real-time (`xiaohongshu-saas/app/api/events.py`)
SSE `/api/v1/events/stream?topic=publish|risk|all` with 200-entry ring buffer, 15s keepalive. `/api/v1/events/recent` for snapshot.

### Backend alerts (`xiaohongshu-saas/app/api/alerts.py`)
Rule engine over 60s sliding window. Rules: risk_block ≥ 3 → critical, publish_fail ≥ 3 → warning.

### Backend cache (`xiaohongshu-saas/app/core/cache.py`)
Thread-safe TTL cache, oldest eviction at max_size.

### pbp-api (`donor-screener-pbp/`)
CSV-backed candidate dataset loader, list/top20/distribution/detail endpoints. Port 8090.

### lakehouse-api (`data-lakehouse/lakehouse_api/`)
Trino wrapper with deterministic seed fallback. KPIs/funnel/series/top-items endpoints. Port 8091.

### docker-compose.yml
3 services with healthchecks, depends_on condition=service_healthy.

### e2e smoke
`scripts/e2e_smoke.py` — per-service healthz, gateway-passthrough, alerts endpoint. Exits 0 only when all green.

## Pending items (from earlier "needs me")

1. **demo.json + demo_*.jpg 是否 push** — still unanswered; current state: not pushed (still local).
2. **`_SendTo-RecycleBin.ps1` 去留** — still untracked. Per earlier user pick option (a) was recommended but not selected.

## Risks known
- Trino online is hypothetical — lakehouse-api falls back to seed if `TRINO_HOST` unset/unreachable.
- Playwright not actually baked into Docker image — `playwright install` is required at runtime if browser automation is needed.
- Recharts + lucide make the bundle ~786KB gzipped 234KB — code splitting deferred.
- Write tool occasionally writes UTF-16; always batch-fix UTF-16 before running tests.
- 110 files in data-lakehouse remain untracked (only the lakehouse-api subset was added in M4a commit).

## M7 — Desktop launcher (.exe GUI) — user ask: "给我个能打开的控制台 或者exe什么的"

User asked for a real GUI app / exe instead of another docker compose dance.
We shipped `scripts/console_gui.py` (pywebview + WebView2) and a `pyinstaller`
build script (`scripts/build_launcher.py`) that produces a double-clickable
`dist/xhs-saas-console/xhs-saas-console.exe`.

| Feature | How |
|---|---|
| Real GUI window | pywebview (uses Win10/11 WebView2, ~0 extra install) |
| Tray fallback | pystray + Pillow (tray menu mirrors Start/Stop/Open/Quit) |
| Embedded UI | HTML/CSS/JS served on http://127.0.0.1:8766/ (dark slate, status pills, rolling log) |
| Subprocess mgr | stdlib `subprocess` + CREATE_NO_WINDOW |
| Status API | http://127.0.0.1:8765/status JSON for scripting |
| Build | `python scripts/build_launcher.py` -> PyInstaller onedir (~15 MB exe + ~85 MB internal) |

Files: `scripts/console_gui.py` (~26 KB), `scripts/build_launcher.py` (~4 KB),
`scripts/requirements-launcher.txt`.  One commit added all three.

Also kept the lite tray-only variant `scripts/tray_launcher.py` (pystray only,
no GUI window) for headless servers.  And the Tkinter variant `console_launcher.py`
will fail at runtime on this machine because Tkinter isn't installed - documented.

## M7.1 — v0.6.1 MSI rebuild (2026-07-05/06)

User: "对GUI把所有的功能放进去 优化一下" — promoted v0.6.0 → v0.6.1 with .ico + cleaner
shortcut wiring.

### What changed
- `installer/wix/product.wxs`:
  - removed `<Component Id="InstallDirMarker" Directory="INSTALLDIR">` attribute
    (WiX rejects `Directory=` when Component is nested inside a `<Directory>`)
  - removed orphan `<ShortcutProperty Id="DesktopAppShortcut" Property="ARPINSTALLPERUSER"/>`
    (ShortcutProperty is not a legal Component child; ARPINSTALLPERUSER is
    already declared as a top-level `<Property>` further down)
- `scripts/_rebuild_onedir_once.py`: NEW. onedir PyInstaller rebuild that
  outputs to `dist/xhs-saas-console/` (what `build_msi.ps1` expects). Uses
  `--icon assets\ico\xhs-saas-console.ico` + `--runtime-tmpdir %LOCALAPPDATA%\xhs-saas-console\runtime`.

### Result
- `dist\xhs-saas-console\xhs-saas-console.exe`  10.78 MB (with embedded icon)
- `installer\output\xhs-saas-console-0.6.1.msi`  343.38 MB
- `msiexec /a` verification:
  - `xhs-saas-console.ico` present in install layout
  - `xhs-saas-console.exe` present in install layout
- TODO next: also push the `_rebuild_onedir_once.py` script + product.wxs
  delta into git (`git add scripts\_rebuild_onedir_once.py installer\wix\product.wxs`).

### Bug of the session
The IDE's Write / StrReplace tools emitted files in **UTF-16 LE** even though
the contents were ASCII. Symptom: `python source code string cannot contain
null bytes` on first run; PowerShell-as-UTF-8 loader (`Get-Content -Encoding
Unicode` → `[IO.File]::WriteAllText(.., UTF8)`) fixed it once per file.
Confirmed via `Format-Hex` first 2 bytes: `FF FE` = UTF-16 BOM.
Workaround added: after any Write/StrReplace/Edit of `.py`, run
`[IO.File]::WriteAllText($path, (Get-Content $path -Raw -Encoding Unicode), [UTF8Encoding]::new($false))`.
**Risk #69 already documented in Risks section — re-confirmed.**

## File locations for next session
- Plan file: `unified_console_tier-1_22e55942.plan.md`
- Workspace: `c:\Users\Hasee\.qclaw\workspace\get_jobs`
- Push target: `https://github.com/zhenyu666-debug/xiaohongshu-Loop.git`