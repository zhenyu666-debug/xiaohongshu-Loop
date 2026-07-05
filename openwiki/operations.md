# Operations

## Install (developer)

```powershell
git clone https://github.com/zhenyu666-debug/xiaohongshu-Loop.git
cd xiaohongshu-Loop
python -m venv xiaohongshu-saas/.venv
.\xiaohongshu-saas\.venv\Scripts\activate
pip install -r xiaohongshu-saas/requirements.txt
```

## Run

```powershell
# backend (also starts scheduler)
cd xiaohongshu-saas
python -m app.main

# console dev server
cd ..\web
npm install
npm run dev
```

Visit `http://localhost:5173` for the UI; the API is on `:8000`.

## Build the installer

```powershell
.\installer\build.ps1
```

Output: `installer/dist/xhs-saas-console-setup-<ver>.msi`. Double-click to
install on Windows. The installer places a desktop shortcut and a Start
menu entry that launches the packaged console.

## Logs

- Application logs: `xiaohongshu-saas/logs/app.log` (rotates daily).
- Scheduler ticks: `xiaohongshu-saas/logs/scheduler.log`.
- Per-publish audit: `xiaohongshu-saas/logs/publish/<note_id>.log`.

## Common failure modes

| Symptom                              | Likely cause                            | Fix                                                   |
|--------------------------------------|-----------------------------------------|-------------------------------------------------------|
| All posts stuck in `publishing`      | Cookie expired                          | Re-login via console -> Captcha tab.                  |
| Captcha image never loads            | Headless browser driver missing         | `playwright install chromium`.                        |
| 429 / rate-limit errors              | Burst posting                          | Lower scheduler frequency in `app/scheduler/config.py`. |
| SSE stream silent                    | Worker process crashed                  | `python -m app.workers.diag` to dump queue state.     |
| MSI install fails with "another version installed" | Previous install present       | Uninstall first via Settings -> Apps.                 |

## Backups

- Cookies: copy `xiaohongshu-saas/data/cookies/*.json` (encrypted at rest
  is a TODO; do not commit).
- SQLite DB: `xiaohongshu-saas/data/app.db`. A nightly `pg_dump`-style
  snapshot is taken by `scripts/backup_db.ps1`.

## Environment variables

| Var                              | Purpose                                                    |
|----------------------------------|------------------------------------------------------------|
| `OPENAI_API_KEY`                 | LLM for `content_factory` (default provider).              |
| `ANTHROPIC_API_KEY`              | Optional alternative provider.                             |
| `XHS_PROXY_URL`                  | Optional outbound HTTP proxy for the publisher.            |
| `XHS_SCHEDULER_ENABLED`          | Set to `0` to disable scheduled jobs (manual mode).        |
| `XHS_LOG_LEVEL`                  | `INFO` default; `DEBUG` to see raw publisher payloads.    |