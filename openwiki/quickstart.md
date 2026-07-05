# Quickstart

## What this repo is

`xiaohongshu-Loop` is the v0.6.0 release of a Xiaohongshu / Douyin content
automation system. It discovers topics, generates notes with LLMs, posts them
through the official Xiaohongshu web flow (with manual cookie login), captures
engagement metrics, and exposes a console UI for monitoring and tweaking.

It is *not* a generic social-media scheduler. It is purpose-built for the
Xiaohongshu (RED) publisher flow, with optional Douyin adapters under
`xiaohongshu-saas/app/channels/`.

## Top-level layout

```
.
├── xiaohongshu-saas/      ← main Python backend (FastAPI + workers)
├── web/                   ← React console frontend
├── packages/              ← electron + node packaging of the console
├── installer/             ← Windows MSI / build scripts for the agent
├── shared/                ← Java / Gradle shared utilities (legacy)
├── docs/                  ← hand-written project documentation
├── scripts/               ← operational scripts (start, fix, OCR, etc.)
├── .github/               ← CI templates (issue / PR / workflows)
├── openwiki/              ← this agent-oriented wiki
└── data/, logs/           ← runtime data (cookies, images, run logs)
```

Directories such as `data-lakehouse/`, `donor-*`, `uml-p-screener/`, `vnpy/`,
`zhilian/`, `liepin/`, `qcc/`, `li_s_additives/`, `front/`, `reports/`,
`memory/`, `ditiediantu/` are **unrelated experimental projects** that share
this checkout but do not participate in the Xiaohongshu pipeline.

## How to run it (developer)

```powershell
# 1. Backend
cd xiaohongshu-saas
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python -m app.main          # or: uvicorn app.main:app --reload

# 2. Console frontend (separate terminal)
cd web
npm install
npm run dev

# 3. End-user installer (one-click MSI)
.\installer\build.ps1        # produces dist/*.msi
```

The system needs at least one Xiaohongshu cookie file in
`xiaohongshu-saas/data/cookies/` before posting will work.

## Where to look first (by task)

| If you need to…                                | Start here                                    |
|------------------------------------------------|-----------------------------------------------|
| Add a new posting endpoint                     | `xiaohongshu-saas/app/api/` + `architecture.md` |
| Change how notes are generated                 | `xiaohongshu-saas/app/content_factory/`       |
| Modify the schedule                            | `xiaohongshu-saas/app/scheduler/`             |
| Touch the React UI                             | `web/` + `source-map.md`                      |
| Add a new channel (e.g. Bilibili)              | `xiaohongshu-saas/app/channels/`              |
| Ship a new installer release                   | `installer/` + `operations.md`                |
| Diagnose a failing pipeline                    | `operations.md` + `logs/`                     |
| Understand domain types                        | `domain.md`                                   |

## Constraints agents must respect

- **Never commit cookie files.** They live in `xiaohongshu-saas/data/cookies/`
  and are git-ignored.
- **Never bump dependency majors** without updating `requirements.txt` and
  asking the user.
- The Xiaohongshu publisher relies on a fragile web flow; rate limits and
  cookie rotation matter. Read `operations.md` before touching it.