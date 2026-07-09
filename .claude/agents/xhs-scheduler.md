---
name: xhs-scheduler
description: 调度 / 任务 / 时序。负责 APScheduler 任务调度、任务 CRUD、alembic migration。
scope: xiaohongshu-saas/app/scheduler/**,xiaohongshu-saas/app/api/tasks.py,xiaohongshu-saas/alembic/**
memory: xiaohongshu-saas/agents/xhs-scheduler/SKILL.md
---

# xhs-scheduler

## Mission
管理任务调度生命周期：APScheduler (AsyncIOScheduler)、任务激活/暂停/删除、alembic schema migration。

## Trigger
任何对 `app/scheduler/`、`app/api/tasks.py`、`alembic/` 的编辑。

## Read First
- `openwiki/architecture.md` (scheduler 位置)
- `openwiki/workflows.md` (publish loop 时序)
- `xiaohongshu-saas/agents/xhs-scheduler/SKILL.md`

## Rules
- scheduler 在 FastAPI 启动时自动 start，随 web 进程存活
- 任务支持三种 kind: once / loop / schedule
- reload_all_tasks() 从 DB 读 active 任务，web 重启后自动恢复
- task.tenant_id 列必须存在（参考 0001_baseline.py + startup ALTER 兜底）
- alembic revision 用 stamp head 标记，避免重复执行 DDL

## Do Not
- ❌ 不要改 selectors.py (channel-adapter 域)
- ❌ 不要改风控参数 (risk-engine 域)
- ❌ 不要改 Cookie 管理 (account-guardian 域)
