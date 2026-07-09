# xhs-console-frontend SKILL.md

## 当前状态
React 控制台已完成基础功能：Accounts 页、Tasks 页、Alerts 页。需优化 dark-mode + 日志过滤 + 卡片间距。

## 关键文件索引
1. `xiaohongshu-saas/web/console/src/pages/` - React 页面组件
2. `xiaohongshu-saas/web/console/src/components/` - UI 组件库
3. `xiaohongshu-saas/web/console/src/hooks/` - useSSE hooks
4. `xiaohongshu-saas/app/api/accounts.py` - 账号 API
5. `xiaohongshu-saas/app/api/tasks.py` - 任务 API

## 最近改动
- 2026-07-09: 创建 SKILL.md，初始化永久记忆
- 2026-07-08: v0.6.2 console API 路径 + 字段对齐

## Next 待办
- [P0] AlertsCenter / TasksList 加 dark-mode toggle
- [P1] 日志按 host (xhs/pbp/lakehouse) 过滤
- [P2] 卡片间距统一 (gap: 10px → 12px)
