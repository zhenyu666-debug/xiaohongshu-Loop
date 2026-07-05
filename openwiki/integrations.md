# Integrations

## Xiaohongshu (RED)

- **What we use**: web flow (login + publish + capture + comment). No
  official API; the publisher drives a Playwright-controlled browser.
- **Where in code**: `xiaohongshu-saas/app/channels/xiaohongshu/`.
- **Risks**:
  - The web flow changes frequently; selectors in `selectors.py` may
    silently rot. After a Xiaohongshu UI update, expect 1-2 days of
    patch work.
  - Aggressive posting triggers captchas and account restrictions.
    Keep posting rate <= 3 notes/hour per account.

## Douyin

- **What we use**: skeleton only. No scheduled jobs wired yet.
- **Where in code**: `xiaohongshu-saas/app/channels/douyin/`.
- **Status**: experimental. Treat as a placeholder for future work.

## LLM providers

- **Default**: OpenAI (gpt-4o-mini for drafts, gpt-4o for hero notes).
- **Pluggable**: `content_factory/providers/` implements a `Provider`
  protocol. Anthropic and local Ollama adapters exist but are untested
  in production.

## Cookies

- Stored as JSON files in `xiaohongshu-saas/data/cookies/`.
- Format: `{"web_session": "...", "webId": "...", ...}` -- whatever
  `playwright` saved after a manual login.
- Refresh: the operator clicks "Re-login" in the console, completes the
  captcha, and the new cookie is written to disk.

## Proxy

- Optional. Set `XHS_PROXY_URL` to route all outbound requests.
- Used to give each account a stable egress IP.

## Frontend tooling

- React 18 + Vite + Tailwind.
- State: React Query + Zustand.
- Charts: Recharts.
- Live updates: native `EventSource` against `/sse/stream`.

## Packaging

- electron-builder for the onefile console.
- Advanced Installer / WiX for the MSI wrapper.
- See `installer/README.md` for the exact pipeline.