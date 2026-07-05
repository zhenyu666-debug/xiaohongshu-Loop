# Architecture

## Runtime topology

```
                  +----------------------------+
                  |       React Console        |
                  |       (web/, :5173)        |
                  +-------------+--------------+
                                | REST + SSE
                                v
       +------------------------------------------------+
       |            FastAPI Backend (app.main)          |
       |                                                |
       |  /api  -->  api/        (HTTP endpoints)       |
       |  /sse  -->  workers/    (long-poll events)     |
       |                                                |
       |  core/  <-- business services                  |
       |  channels/ <-- xiaohongshu, douyin drivers     |
       |  content_factory/ <-- LLM note generation      |
       |  scheduler/  <-- APScheduler jobs              |
       |  db/   <-- SQLAlchemy + SQLite                 |
       |  models/  <-- ORM                              |
       |  schemas/ <-- pydantic                         |
       +-------------+----------------------------------+
                     | local FS + cookies
                     v
              +------------------+
              |   data/, logs/   |
              +------------------+
```

## Module boundaries

| Module                              | Responsibility                                                              |
|-------------------------------------|-----------------------------------------------------------------------------|
| `app/api/`                          | HTTP routes. Thin layer; delegates to `core/`.                              |
| `app/core/`                         | Business logic. Services used by both `api/` and `workers/`.               |
| `app/channels/xiaohongshu/`         | Xiaohongshu-specific publisher, capture, comment.                            |
| `app/channels/douyin/`              | Douyin adapter (skeleton, not wired to prod schedule).                      |
| `app/content_factory/`              | Prompt building, LLM call wrappers, template rendering.                     |
| `app/scheduler/`                    | APScheduler jobs: post, capture, refresh-cookies, retention.               |
| `app/workers/`                      | Background async tasks; SSE streams for live updates.                       |
| `app/db/` + `app/models/`           | Persistence; SQLite by default, swappable engine.                           |
| `app/schemas/`                      | Pydantic models for request/response.                                       |
| `app/main.py`                       | App factory, lifespan, CORS, route mounting.                                |

## Data flow (publish a note)

1. `scheduler/` triggers a job at the configured time.
2. `core/` picks a topic, calls `content_factory/` to render the note text
   and image prompt.
3. The composed payload goes to `channels/xiaohongshu/publisher.py`, which
   loads cookies from `data/cookies/` and drives the headless browser flow.
4. Result (success/failure, post id) is written via `db/` and emitted as an
   SSE event from `workers/`.
5. `web/` re-renders the dashboard panel from the SSE stream.

## Process model

There are two long-running processes:

- **API process** -- FastAPI, also runs the scheduler in-process (default).
- **Console dev server** -- Vite, served at `:5173`, proxies `/api` to `:8000`.

A packaged release uses **one Electron-wrapped console** (`packages/`) which
embeds the Python backend as a sidecar (`xhs-saas-console.exe`) launched on
startup.

## Build / packaging

- **Backend wheel**: `python -m build` produces `xiaohongshu-saas/dist/*.whl`.
- **Console onefile exe**: `packages/xhs-saas-console/` (electron-builder).
- **Windows MSI**: `installer/build.ps1` bundles the onefile exe plus
  shortcuts and uninstaller.