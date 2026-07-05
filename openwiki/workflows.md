# Workflows

The repo supports four day-to-day loops. Each has a producer, a consumer, and
a state store.

## 1. Publish loop

- **Trigger**: scheduler cron (`app/scheduler/jobs/publish.py`).
- **Steps**:
  1. Pick a pending note from `notes` table.
  2. Render with `content_factory` (template + LLM).
  3. Drive the Xiaohongshu publisher (`channels/xiaohongshu/publisher.py`).
  4. Write back the published URL, capture timestamp.
- **Failure modes**: cookie expired, captcha, network. Each is logged and
  retried with backoff; persistent failures move the note to `failed` and
  emit an SSE event for the console.

## 2. Capture loop

- **Trigger**: scheduler cron (`capture_metrics` job).
- **Steps**:
  1. For each post published in the last N days, load its URL.
  2. Read likes / comments / saves from the page.
  3. Persist to `metrics` table.
- Used by the dashboard's `Top posts` panel.

## 3. Comment loop

- **Trigger**: scheduler cron or manual button in console.
- **Steps**:
  1. For each target post, generate a reply with `content_factory`.
  2. Post via `channels/xiaohongshu/commenter.py`.
  3. Record in `comments` table.

## 4. Cookie refresh loop

- **Trigger**: scheduler cron (every 6 hours by default).
- **Steps**:
  1. Hit Xiaohongshu with the saved cookie.
  2. If 401/expired, mark cookie as `needs_login`.
  3. Operator re-logs in via console; cookie file is overwritten.

## Console interactions

The React console (`web/`) exposes a tabbed UI:

- **Dashboard** -- KPI cards + recent activity SSE.
- **Posts** -- list of notes, status, retry button.
- **Schedule** -- cron table, toggle jobs.
- **Captcha / Login** -- re-login flow when cookie expires.
- **Settings** -- LLM provider, rate limits, image model.

Mutations hit `/api/*`; live updates come through `/sse/stream`.