# LOOP-STATExhs.md

Last updated: 2026-07-06 10:50 UTC+8
Session: 0.6.2 release — 修完所有待办 + 打新 MSI

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

## 2026-07-06 第四次 session 改动（方案 C-lite）

### 背景
- 用户打开 v0.6.1 console exe（已安装）后，看到三个服务卡片的灯一直是灰色
- 之前的 exe 上 console_gui.main() 启动后**没有自动调 start_all()**（必须用户手动点"启动服务"按钮）
- 而就算点了按钮，pbp-api / lakehouse-api 也会失败：
  - PyInstaller bootloader 把 sys.executable 设成了 launcher 自己，`-m uvicorn` 静默被吞
  - donor-screener-pbp / data-lakehouse 源码早就搬到私有仓库（CHANGELOG 0.6.1），本地只剩 `__pycache__/*.pyc`

### item: console SERVICES 加 `enabled` 字段
- **status**: done
- **改动** (scripts/console_gui.py):
  - 每个 service 加 `enabled: bool` 字段，默认 True 保持后向兼容
  - 实际值：xhs-saas=True, pbp-api=False, lakehouse-api=False（带注释说明源码已搬走）
  - `_spawn()`：disabled 直接 return，不 spawn，并把 `last_error` 标 "disabled in console config"
  - `_supervise()`：disabled 服务 `continue`，不参与健康检查，不污染 `all_healthy`
  - `snapshot()`：disabled 服务的 `state` 字段是 `"disabled"`（区别于 `"stopped"`），明确带 `enabled: false`
  - `start_all()`：先列 enabled/disabled 两个 list，log 里打印"正在启动 N 个服务（M 已禁用）"
- **下次注意**: 当未来 pbp_api / lakehouse_api 源码拿回来后，把 `enabled` 改回 True 即可，snapshot / GUI / supervise 都不需要改

### item: 前端 GUI 显示 disabled 卡片（灰色虚线边框）
- **status**: done
- **改动** (scripts/console_gui.py HTML/CSS/JS):
  - 加 `.state.disabled` 徽章样式（深灰底 + dashed border）+ `.card.disabled-card` 整卡半透明 + 虚线
  - 卡片 `<div class="card">` 加 `id="card-{name}"`，`_build_card_index` 加 `el: document.getElementById('card-<name>')`
  - `updateState()` JS：发现 `sv.state === 'disabled'` → 加 `.disabled-card` 类 + 显示"○ 未启用"
  - `all_healthy` 计算时**忽略 disabled**，所以就算两个 disabled 也只算 xhs-saas 一个
- **下次注意**: disabled 卡片状态是"○ 未启用"，不是"● 已停止"——用户能一眼看出来这是"被主动禁用"而不是"出了故障"

### item: main() 自动调 start_all()（修 Bug 1）
- **status**: done
- **改动** (scripts/console_gui.py main()):
  - 在 `webview.start()` 之前、status/gui server 启动之后，try/except 包一层 `launcher.start_all()`
  - try/except 是为了不让自动启动的失败阻止 WebView 打开（用户至少能看到日志）
- **下次注意**: 这是改的"启动后自动跑"，不是"启动前等待"；如果某个 enabled 服务需要几十秒启动，WebView 窗口会立刻显示"启动中…"状态（supervisor 每 1.5s 轮询）

### item: 修复 5 个 xhs-saas UTF-16 文件
- **status**: done
- **改动**（PowerShell `[System.IO.File]::WriteAllText($f, $content, [System.Text.UTF8Encoding]::new($false))` 转码）:
  - `xiaohongshu-saas/app/api/auth.py` (8650 nulls)
  - `xiaohongshu-saas/app/api/billing.py` (4297 nulls)
  - `xiaohongshu-saas/app/api/tenants.py` (7423 nulls)
  - `xiaohongshu-saas/app/core/auth.py` (5798 nulls) ← 这个最先暴露，因为 accounts.py 第一行 import 它
  - `xiaohongshu-saas/app/core/security.py` (4926 nulls)
- **根因**: HEAD 这些文件本来就是 UTF-8，working tree 被某次工具保存改成了 UTF-16 LE + BOM（跟 CHANGELOG.md 之前那次的根因一样）
- **影响**: git diff 现在把它们当 binary file 处理（`Bin N -> M bytes`），下次改动才会正常显示 text diff
- **下次注意**:
  - 当 workspace 又出现 NUL bytes 时，记得先 `Format-Hex <file> | Select -First 2` 看一下首字节（FF FE = UTF-16 LE BOM，EF BB BF = UTF-8 BOM，FF FE 22 00 = UTF-16 LE 文本）
  - 编辑器或 sync 工具保存时如果把"另存为"对话框里默认选错，会从 UTF-8 变成 UTF-16

### item: 暴露下一个真实问题（不在本次 commit 范围）
- **status**: open（需要下一个 commit 修）
- **问题**: xhs-saas 启动时 uvicorn 报 `ImportError: email-validator is not installed, run 'pip install pydantic[email]'`
- **来源**: `xiaohongshu-saas/app/api/auth.py` 用 `EmailStr` pydantic 字段
- **修法**: `pip install 'pydantic[email]'` 或 `pip install email-validator`
- **意义**: **这正是本次改造的核心收益之一**——以前 PyInstaller bootloader 静默吞错，用户只看到"灯是灰的"；现在 stderr 直接流进 launcher.log，用户能看懂下一步该做什么
- **下次注意**: 装好 email-validator 后还要装 `pyproject.toml` 里列的其他 optional deps（python-jose、python-multipart 之类），用 `pip install -e ".[dev]"` 一把搞定

### 剩余待办（v0.6.2 之后）
| 优先级 | 待办 | 状态 |
|---|---|---|
| P0 | console 自动启动 | ✅ main() 调 start_all() (c494584) |
| P0 | pbp-api / lakehouse-api 不再假装失败 | ✅ enabled=True，从 backup 恢复源码 (b00019c) |
| P0 | xhs-saas 真实错误能看见 | ✅ PyInstaller 不再吞 stderr |
| P0 | xhs-saas 缺 email-validator | ✅ pyproject.toml 加 dep (692762e) |
| P0 | xhs-saas NameError: Tenant | ✅ import 搬到 _seed_default_tenant 里 (692762e) |
| P0 | xhs-saas NoForeignKeysError | ✅ 删 User.tenant / Tenant.users (692762e) |
| P0 | v0.6.2 MSI | ✅ 159 MB, msiexec /a verify 通过 (fccd4b7) |
| P1 | 重新打 console exe + MSI | ✅ done as part of fccd4b7 |
| P1 | 清理 src/ untracked 残留 | ✅ .gitignore 加 src/ (b00019c) |
| P1 | pbp_api / lakehouse_api 源码追踪 | ✅ .gitignore 改选择性忽略 data-lakehouse/ (b00019c) |
| P2 | Release v0.6.2 到 GitHub | ❌ `installer/build.ps1 -Version 0.6.2 -Publish` 还需要 gh auth |
| P2 | dev sqlite schema drift (tasks.tenant_id 列缺失) | ❌ alembic migration 没跑，或加 ALTER TABLE；不阻塞启动但 reload_all_tasks 会 throw |
| P2 | pbp-api / lakehouse-api end-to-end 测试 | ❌ 没跑过完整 chain（api/v1/pbp → 8090）—— 我测试时 gateway 配的端口和我手动启动的不一致 |
| P2 | candle CNDL1098 / CNDL1077 警告 | ❌ cosmetic；warning 不阻塞 build，但 product.wxs 可以小修 |
| P2 | onefile exe 195 MB 单独 release | ❌ release 0.6.1 时附带的 onefile exe，0.6.2 没重新打（如需要按 c51aaf4 的 sibling asset 流程补打） |

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

## 已推送的改动（最近三次 commit）

```
commit fccd4b7 - release: v0.6.2 MSI (159 MB)
commit b00019c - feat(console): restore pbp-api + lakehouse-api from backup
commit 692762e - fix(xhs-saas): email-validator dep + Tenant import + User.tenant schema
推送时间: 2026-07-06 10:50 UTC+8

692762e (3 files):
  M xiaohongshu-saas/pyproject.toml                            (+1 line)
  M xiaohongshu-saas/app/db/session.py                         (+1 line)
  M xiaohongshu-saas/app/models/orm.py                         (-2 lines, deleted bad relationships)

b00019c (15 files):
  A donor-screener-pbp/pbp_api/{__init__,dataset,main}.py     (3 files)
  A donor-screener-pbp/pbp_api/routers/{__init__,candidates,health}.py (3 files)
  A data-lakehouse/lakehouse_api/{__init__,client,main,seed}.py (4 files)
  A data-lakehouse/lakehouse_api/routers/{__init__,analytics,health}.py (3 files)
  M scripts/console_gui.py                                    (enabled pbp-api/lakehouse-api, dropped 暂未启用 labels)
  M .gitignore                                                (surgical data-lakehouse/ patterns + add src/)

fccd4b7 (2 files):
  M dist/xhs-saas-console/xhs-saas-console.exe                (rebuilt via PyInstaller 6.x on Python 3.11)
  A installer/output/xhs-saas-console-0.6.2.msi               (159 MB, msiexec /a verified)
```

## 验证记录

```bash
# 1. pip install (now includes email-validator)
pip install -e ".[dev]"                  # email-validator 2.3.0 + 9 deps

# 2. xhs-saas boots clean
python -m uvicorn app.main:app --port 18770
# -> "Application startup complete. Uvicorn running on http://127.0.0.1:18770"
# -> POST /api/auth/signup returns {"user_id":1,"tenant_id":"smoke-tenant-a12c",...}

# 3. pbp-api serves data
python -m uvicorn pbp_api.main:app --port 18771
# -> GET /healthz -> {"status":"ok","service":"pbp-api"}
# -> GET /api/candidates -> 50 ranked molecules

# 4. lakehouse-api boots
python -m uvicorn lakehouse_api.main:app --port 18772
# -> GET /healthz -> {"status":"ok","service":"lakehouse-api"}

# 5. MSI verify
msiexec /a installer/output/xhs-saas-console-0.6.2.msi
# -> installed/xhs-saas-console/xhs-saas-console.exe present
# -> installed/xhs-saas-console/xhs-saas-console.ico present
```

验证: `python scripts/console_gui.py` 跑通，console 自动启动 xhs-saas，`/status` JSON
输出符合预期（xhs-saas enabled, pbp-api/lakehouse-api state=disabled）
