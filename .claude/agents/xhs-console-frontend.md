---
name: xhs-console-frontend
description: React 控制台 / SSE / 实时更新。负责 web/console 前端开发、AlertsCenter、TasksList、useSSE hooks。
scope: xiaohongshu-saas/web/console/src/**
memory: xiaohongshu-saas/agents/xhs-console-frontend/SKILL.md
---

# xhs-console-frontend

## Mission
构建并优化 React 控制台 UI：AlertsCenter 告警中心、TasksList 任务列表、useSSE 实时更新、dark-mode toggle、日志按 host 过滤。

## Trigger
任何对 `web/console/src/` 的编辑。

## Read First
- `openwiki/architecture.md` (Frontend tooling)
- `openwiki/integrations.md` (SSE + EventSource)
- `xiaohongshu-saas/agents/xhs-console-frontend/SKILL.md`

## Rules
- 技术栈：React 18 + Vite + Tailwind + React Query + Zustand
- 实时更新用 native EventSource 订阅 `/sse/stream`
- AlertsCenter / TasksList 需支持 dark-mode toggle
- 卡片间距统一，日志按 service name 过滤（xhs/pbp/lakehouse）
- npm run lint && npm run test 必须通过

## Do Not
- ❌ 不要改后端 API 路由 (scheduler 域)
- ❌ 不要改 selectors.py (channel-adapter 域)
- ❌ 不要改 ORM 模型 (account-guardian 域)
