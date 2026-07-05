# OpenWiki for xiaohongshu-Loop

This directory contains agent-oriented documentation for the `xiaohongshu-Loop`
monorepo, generated in the [OpenWiki](https://github.com/langchain-ai/openwiki)
convention. Files here give coding agents long-term context about the codebase
so they can answer questions, plan changes, and produce patches without
re-reading every source file every session.

## Start here

- [quickstart.md](./quickstart.md) — what this repo is, how to run it, where
  to look first.
- [architecture.md](./architecture.md) — module boundaries, runtime topology,
  data flow, and process model.
- [workflows.md](./workflows.md) — the day-to-day loops (publish, capture,
  schedule, dashboard).
- [domain.md](./domain.md) — domain concepts: accounts, channels, content
  factories, notes, comments.
- [operations.md](./operations.md) — install, run, monitor, recover.
- [integrations.md](./integrations.md) — Xiaohongshu / Douyin APIs, cookies,
  proxies, third-party tooling.
- [testing.md](./testing.md) — test layout, fixtures, how to add a test.
- [source-map.md](./source-map.md) — concrete file/folder index.

If you only have time for one file, read `quickstart.md`, then jump to the
specific topic.