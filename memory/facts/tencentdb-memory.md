# tencentdb-memory — distilled reference

> Source: `memory/references/tencentdb-agent-memory/TencentDB-Agent-Memory-main/`
> Repo: <https://github.com/TencentCloud/TencentDB-Agent-Memory>
> License: MIT (Tencent, 2026) — redistribution OK
> Mirrored: 2026-07-07 (zip download, no `.git`)
> Stars at mirror time: 6730
> Tagline: *"Agents remember, Humans innovate."* — symbolic short-term memory + layered long-term memory.

---

## What this repo actually is

A **plugin** (npm: `@tencentdb-agent-memory/memory-tencentdb`) that gives OpenClaw or Hermes agents a persistent local **long-term memory** with **layered drill-down** (never flat-vector recall), plus **short-term symbolic compression** (Mermaid canvas + offloaded raw logs) for long tasks.

It is **not** a library you install into a Python/Java project. It is **not** an SDK. It is a TypeScript plugin that hooks into a specific agent runtime (OpenClaw or Hermes). For our workspace, it is **a reference design** — a credible, production-grade pattern to model our own memory layer on.

Two design pillars (per README 뿯½"Core Technology"):

1. **Memory layering** — progressive disclosure with heterogeneous storage.
2. **Symbolic memory** — Mermaid canvases + offloaded logs for in-task context.

---

## The 4-tier long-term pyramid

Read literally: there are **four** named tiers L0–L3 plus a parallel **symbolic short-term** layer.

| Tier | Name            | Format                              | Stored in       | Purpose                                                | Cadence                         |
| ---- | --------------- | ----------------------------------- | --------------- | ------------------------------------------------------ | ------------------------------- |
| L0   | **Conversation** | raw dialogue turns                  | SQLite          | ground-truth evidence, full text                       | every turn (auto-capture)       |
| L1   | **Atom**        | atomic facts (one fact per line)    | SQLite + sqlite-vec | re-usable snippets across sessions                  | every N turns (default 5)       |
| L2   | **Scenario**    | scene blocks (Markdown)             | Markdown files  | recurrent situations / solution patterns               | persona-triggered, min interval 15 min |
| L3   | **Persona**     | user profile (Markdown)             | Markdown file   | long-running preferences, voice, goals                 | every N new memories (default 50) |
| —    | **Canvas**      | task state (Mermaid + node_id)      | Markdown + refs/*.md | in-task symbolic compression                     | per task; replaced on resume    |

Plus a **short-term offload** track (`offload/`):

- full tool logs 뿯↽ `refs/*.md` on disk (lossless)
- state transitions 뿯↽ compact Mermaid graph (in context)
- drill-down: `node_id` 뿯↽ `refs/<id>.md` when LLM needs the raw text

---

## Drill-down contract (the key invariant)

`Persona 뿯↽ Scenario 뿯↽ Atom 뿯↽ Conversation` — every upper-layer claim links back to lower-layer evidence by **`result_ref` / `node_id`**. No irreversible summarization.

When LLM asks *"why does the user hate Tailwind?"*:

1. L3 Persona has `user_style: hates-css-frameworks, ref: scene/2024-10-12-atomic-react.md`
2. L2 Scenario block cites L1 atoms
3. L1 Atom has `source_ref: conv/2024-10-12-003#turn5`
4. L0 Conversation is the raw turn.

White-box debuggability: every layer is **human-readable Markdown or inspectable SQLite** — never an opaque embedding dump.

---

## Heterogeneous storage rationale

- Bottom (facts / logs / traces) 뿯↽ SQLite + sqlite-vec 뿯↽ robust full-text + vector recall (`hybrid = BM25 + embedding + RRF`)
- Top (personas / scenes / canvases) 뿯↽ Markdown 뿯↽ high information density, diffable, and editable by humans

Lower layers preserve evidence; upper layers preserve structure. That sentence alone is worth stealing.

---

## Pipeline schedule (the knobs)

| Knob                                            | Default | Meaning                                             |
| ----------------------------------------------- | ------- | --------------------------------------------------- |
| `pipeline.everyNConversations`                  | 5       | Trigger L1 extraction every N turns                 |
| `pipeline.enableWarmup`                         | true    | New session: 1뿯↽2뿯↽4뿯↽… extracts until cadence          |
| `pipeline.l1IdleTimeoutSeconds`                 | 600     | Trigger L1 after user idle                          |
| `pipeline.l2DelayAfterL1Seconds`                | 10      | Stagger L2 after L1                                |
| `pipeline.l2MinIntervalSeconds`                 | 900     | Never re-L2 same session faster than this           |
| `pipeline.l2MaxIntervalSeconds`                 | 3600    | Upper bound on L2 cadence                          |
| `extraction.maxMemoriesPerSession`              | 20      | Cap on L1 atoms per pass                           |
| `extraction.enableDedup`                        | true    | Vector dedup / conflict detection                  |
| `recall.strategy`                               | hybrid  | `keyword` / `embedding` / `hybrid` (RRF)            |
| `recall.maxResults`                             | 5       | Items per recall                                   |
| `recall.scoreThreshold`                         | 0.3     | Below this, skip                                  |
| `persona.triggerEveryN`                         | 50      | New L3 Persona every N new L1 atoms                |
| `capture.l0l1RetentionDays`                     | 0       | 0 = never cleanup; else ≥3                         |
| `offload.enabled` + `mildOffloadRatio`          | 0.5     | When context fills 50 %, offload verbose logs      |
| `offload.aggressiveCompressRatio`               | 0.85    | When context fills 85 %, compress aggressively     |

---

## Mapping to our workspace memory

Our current AGENTS.md (L53-83) has **three** tiers. The repo has **four**. The 4th maps naturally onto a *reference / upstream-mirror* role that our tier-3 (Episodic) was never asked to fill.

| TencentDB tier | Our tier          | Our path                       | What lives there                              | When to write                            |
| -------------- | ----------------- | ------------------------------ | --------------------------------------------- | ---------------------------------------- |
| L0 Conversation | Episodic          | `memory/YYYY-MM-DD.md`, `memory/sessions/...` | raw session log                          | end of session                           |
| L1 Atom         | Semantic (atomic) | `memory/facts/<topic>.md`      | one fact per line, retrievable                | decision/lesson learned                  |
| L2 Scenario     | Semantic (scene)  | `memory/facts/<topic>.md` (scene-block style) | Markdown scene block with refs             | recurring situation appears              |
| L3 Persona      | Semantic (profile)| `memory/facts/user-profile.md` | long-running preferences / voice              | weekly during heartbeat review           |
| Reference (new) | **Reference**     | `memory/references/<repo>/`   | upstream repo mirror, untouched, README-driven | when a pattern is worth stealing         |
| — (none)        | Procedural        | `.cursor/skills/`, `ralph/skills/` | how-tos / SOPs                              | when a workflow is repeatable            |

The key adoption: **Promote the three-tier heading to four-tier by adding `memory/references/<repo>/` for upstream mirrors and a one-line cross-reference in the matching `memory/facts/<topic>.md`.** Never let the raw reference be the only thing a future session reads — distill first, mirror second.

---

## Concrete adoption candidates in `get_jobs`

Plenty of cross-cutting patterns here. These are real places where adopting a piece of this would help — not theoretical.

1. **`xhs-saas` publish-failure memory (L1 atoms).** Currently `_maybe_rotate` resets `fail_streak` inline. We could promote each `mark_failure(...)` call to write one L1-style atom row with `kind`, `error_class`, `account_id`, `task_id`, `timestamp`, plus a `result_ref` linking to the daily memory file. Then `cool_down_minutes_after_fail` becomes a derived query ("any atom in last 30 min with this account?"), not a hardcoded constant.

2. **`memory/facts/skills.md` (L3 persona for skills).** Today it's just a flat table. Promote it to a per-skill L3-style entry with `voice, scope, do_not_use_when` plus `result_ref: scene/<when-skill-applies>.md`. Future sessions can recall it via grep, no LLM required.

3. **Mermaid canvas for active agent runs (symbolic short-term).** The current `LOOP-STATExhs.md` is a 249-line focus file. Per the TencentDB pattern, we should keep the in-context snippet as a compact Mermaid graph (`extract_xhs 뿯↽ check_cookie 뿯↽ publish 뿯↽ record`) and offload the verbose event ledger to `memory/sessions/<date>/<run>.md`. The model only ever sees the graph unless it asks for a node.

4. **Scene blocks for recurring ops (L2).** Two obvious scene blocks to author once:
   - `memory/facts/scene-xhs-cookie-expired.md` — symptoms (heartbeat green but publisher wall), drill-down (cookie file 뿯↽ chromium flag 뿯↽ window.chrome.runtime)
   - `memory/facts/scene-playwright-headless-vs-headed.md` — when dev must run headed, when CI must run headless, anti-detection toggles

5. **Hybrid recall at workspace level (L1 search tool).** Right now `memory/` doesn't have an index. Adding `memory/facts/INDEX.md` (a one-line summary per fact file) is the poor-man's BM25; SQLite + sqlite-vec would be the rich version. Either way, eventual project.

---

## Do NOT adopt (without care)

These belong to Tencent's stack — bringing them in naively creates tech debt.

- **The `@tencentdb-agent-memory` plugin itself** — it hooks OpenClaw or Hermes, neither of which runs in this workspace. Wrong shape.
- **The Hermes Gateway** (`/8420/health`) — we have no use for an HTTP gateway in front of memory.
- **TCVDB backend** (Tencent Cloud Vector Database) — paid SaaS. Replace with local SQLite + sqlite-vec, which is the plugin's own default anyway.
- **Mermaid canvas as the only in-task state** — overkill for our 4-step publish loops; useful only if we ever run a >20-step multi-agent plan.
- **`tdai_memory_search` / `tdai_conversation_search` RPC tool names** — keep our own simple `grep`-able filenames.
- **Skill-migration scripts** (`SKILL-MIGRATION.md`) — relevant only if we ever ship a plugin and rename it. Not now.

---

## Open questions for future sessions

1. Should `memory/facts/skills.md` move to a SQLite-backed index (BM25 + vector) with one row per fact? Cheap, but adds a runtime dep.
2. Should we add an **L2 scene directory** `memory/facts/scenes/*.md` separately from atomic facts, or keep them flat under `memory/facts/`?
3. Is there a time-windowed "persona refresh" cadence worth wiring into heartbeats? (Default idea: every Friday.)
4. Should `LOOP-STATExhs.md` be the first **symbolic canvas** we trial? (It's the only long focus file we have.)

---

## Source-of-truth pointers (in the mirror)

When a future session needs to verify or extend this distillation, open these files first:

- `TencentDB-Agent-Memory-main/README.md` — full feature set, benchmarks, plugin install.
- `TencentDB-Agent-Memory-main/SKILL.md` — install + config procedure + golden templates.
- `TencentDB-Agent-Memory-main/src/core/types.ts` — `RuntimeContext`, `HostAdapter`, `LLMRunner` interfaces (the cleanest single-file summary of how the layers talk).
- `TencentDB-Agent-Memory-main/src/core/tdai-core.ts` — entry point that wires capture/extract/recall.
- `TencentDB-Agent-Memory-main/CHANGELOG.md` — history; useful when asking "what changed between version X and Y".
