# LOOP-STATExhs.md

Last updated: 2026-07-03 16:16 UTC+8
Session: 自动发帖打通

## 架构摘要

- 调度器：APScheduler (AsyncIOScheduler) 在 FastAPI 启动时自动启动，随 web 进程存活
- 任务执行：`run_task_once()` (runner.py)，按 task.account_ids 遍历账号，串行发布
- 内容生成：factory.render() 从 `data/templates/{key}.json` 读取模板，支持 `{emoji}` 占位
- 风控：risk_evaluate() 按 日配额/小时配额/冷却/暖机 逐级拦截
- 适配器：XiaohongshuAdapter（Playwright）+ DouyinAdapter（stub）
- Cookie 存储：`data/cookies/{account_id}.json`
- 模型：Account / Content / Task / Publish（SQLAlchemy ORM，sqlite 默认）

## 已完成的改动

### item: 评估断点
- **status**: done
- **改动**: 探索了整个调度链路，确认 3 个关键断点

### item: 修 XiaohongshuAdapter._load_context + publish 兜底
- **status**: done
- **改动** (xiaohongshu-saas/app/channels/xiaohongshu/adapter.py):
  - 方法 `_browser` 重命名为 `_get_browser`，消除与方法作为属性名的歧义
  - `_load_context`: 增加 context pages 健康检查（尝试访问 `ctx.pages`），已关闭的 context 被静默丢弃重建；cookie_path 为空时 fallback 到 `cookie_path_for(account.id)`
  - `_load_context` AccountError 信息增强：包含 cookie_path 路径和修复命令
  - `publish()`: AccountError 不再 raise，直接返回 `PublishResult(success=False, error="account not logged in...")`
  - `publish()` 其他异常兜底：`error=f"{exc.__class__.__name__}: {exc}"` 保留类型名方便排查
- **下次注意**: 缺失 cookie 时会返回 PublishResult 而非抛异常，runner.py 不需要额外处理

### item: 创建 demo 模板 + 占位图片
- **status**: done
- **改动**: 新建 `data/templates/demo.json`（穿搭主题）；PIL 生成 3 张 800x800 JPEG 占位图 `data/images/demo_{1,2,3}.jpg`；`scripts/seed_demo.py` 加 `_gen_placeholder_images()` 函数，每次 seed 自动生成图片（幂等）
- **下次注意**: 图片是占位色块，真实发帖需要真实图片文件

### item: console API 路径 + 字段对齐
- **status**: done
- **改动**:
  - Accounts.tsx: `id` 类型 `number` → `string`，`/accounts/{id}/login/` → `/accounts/{id}/login`（后端无尾斜杠）
  - Tasks.tsx: `/scheduler/tasks/` → `/tasks/`，`/run/` → `/run`，`PATCH /scheduler/tasks/{id}/` → `/tasks/{id}/`，`t.last_run` → `t.last_run_at`，`t.schedule` → 显示 `interval_minutes` 或 `cron`
  - schemas/__init__.py: `AccountOut` 加 `@computed_field` `cookies_valid`，pydantic import 补 `computed_field`
- **下次注意**: Accounts 页的 `id` 是 string（账户 ID），Tasks 页的 `id` 是 int（任务 ID）

## 2026-07-03 第三次 session 改动

### item: 仓库根 README 装修
- **status**: done
- **改动**:
  - 新建仓库根 `README.md`（9199 B）：Hero + 8 枚 shields.io for-the-badge 徽章条 + 核心能力矩阵表 + Mermaid 架构图（flowchart TB 五层解耦）+ Demo 占位（3 张 via.placeholder.com 待替换为真实 GIF）+ 三种快速开始（Docker / 本地 / React 控制台）+ 渠道适配器扩展代码示例 + 风控默认策略表 + Roadmap（含新加的"仓库根 README 装修"项）+ Contributing / Disclaimer / License + star history 社交徽章
  - 主色调：小红书红 `#FF2442` / `#FF6B81` 配深灰 `#1a1a1a`
  - 4 个 GitHub callout：`> [!IMPORTANT]` / `[!TIP]` / `[!NOTE]` / `[!WARNING]`
- **附带**: 原仓库根残留的 Java get-jobs README（未被 git tracked）已备份到 `docs/legacy/get-jobs-readme.md`，避免误删历史内容
- **验证**: render_check 脚本——HTML 闭合 27=27、Mermaid 1 块 0 节点带空格、shields 链接 8 条、相对链接 7 条、表格 19 行、callout 4 个，全部通过
- **下次注意**:
  - push 后到 GitHub 手动替换 via.placeholder.com 占位图为真实 demo GIF（`docs/demo-loop.gif`）
  - shields.io 链接需要 push 后才能拉到真实 stars/forks 数据（推送前会显示 0）

### item: 修复 _maybe_rotate 逻辑 bug
- **status**: done
- **改动** (adapter.py `_maybe_rotate`):
  - 阈值内：直接调 `_load_context()` 返回活 context（不依赖返回值）
  - 阈值到达：关闭旧 context，重新创建并直接存回 `self._contexts`
  - 消除了 `publish()` 中丢弃 `_maybe_rotate` 返回值的 bug
- **下次注意**: `_maybe_rotate` 现在是纯内部方法，不依赖返回值正确性

### item: APScheduler 持久化 next_run_at
- **status**: done
- **改动** (scheduler/__init__.py `_tick_task`):
  - 执行成功后同步写 `task.last_run_at` 和 `task.next_run_at`（loop 任务按 interval 推进）
  - `reload_all_tasks()` 每次从 DB 读 active 任务，web 重启后自动恢复
- **下次注意**: 进程崩溃时最后还未 commit 的执行会丢失（无两阶段提交）；CronTrigger 任务由 APScheduler 内部管理 next_run_time，不受此影响

## 剩余待办（可后续处理）

| 优先级 | 待办 | 状态 |
|---|---|---|
| P0 | 扫码登录 | ✅ 已实现：`python -m scripts.harvest_xhs_cookie --account-id acc_001` |
| P0 | 模板图片 | ✅ PIL 占位图已生成，真实发帖需真实图片 |
| P1 | API 端点 | ✅ 后端 `/api/{accounts,tasks,dashboard/summary}` 已就位 |
| P1 | console cookies_valid | ✅ AccountOut 加了 computed_field |
| P2 | Tasks.tsx 字段对齐 | ✅ `t.last_run` / `t.schedule` 已修 |
| P2 | _maybe_rotate bug | ✅ 重写内部逻辑 |
| P2 | APScheduler 持久化 | ✅ `_tick_task` 写 `next_run_at` 到 DB |
| P2 | DouyinAdapter 未实现 | 三个方法 raise NotImplementedError |

## 测试命令

```bash
cd xiaohongshu-saas

# 单元测试
python -m pytest -q tests

# 扫码登录
python -m scripts.harvest_xhs_cookie --account-id acc_001

# 初始化 demo 数据
python -m scripts.seed_demo

# 手动触发一次发帖（前提：已扫码 + 已激活任务）
python -c "
import asyncio, sys
sys.path.insert(0, '.')
from app.db.session import SessionLocal
from app.models import Task
from app.scheduler.runner import run_task_once
async def go():
    async with SessionLocal() as s:
        t = await s.get(Task, 1)
        if t:
            r = await run_task_once(s, t)
            print([p.status for p in r])
asyncio.run(go())
"
```

## 未 push 的改动（需在 git bash 手动执行）

```bash
cd c:/Users/Hasee/.qclaw/workspace/get_jobs
git add README.md \
        xiaohongshu-saas/app/channels/xiaohongshu/adapter.py \
        xiaohongshu-saas/app/schemas/__init__.py \
        xiaohongshu-saas/scripts/seed_demo.py \
        xiaohongshu-saas/app/scheduler/__init__.py \
        xiaohongshu-saas/web/console/src/pages/Accounts.tsx \
        xiaohongshu-saas/web/console/src/pages/Tasks.tsx \
        xiaohongshu-saas/data/images/ \
        xiaohongshu-saas/data/templates/demo.json \
        docs/legacy/get-jobs-readme.md
git commit -m "feat: 仓库根 README 装修 + scheduler 持久化 + 占位图 + 备份 Java README"
git push origin main
```
