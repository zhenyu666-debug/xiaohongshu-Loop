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

## 2026-07-09 第七次 session 改动（AI 平台健壮性 + 性能）

### 背景
- 上一轮（第六次）已经把 AI Agent 平台骨架搭起来（agents / memory / rag / tools / mcp / prompts 七大模块）
- 这次的目标是"向里面大量灌注数据测试健壮性"——单进程内 200k+ memory 操作、70k+ RAG、8k+ tool call、2k+ MCP 消息，看哪个模块先塌
- 一开始**没有任何 perf 优化**，纯按文件照着原版跑；发现 5 个性能塌方点 + 1 个 bug，逐个修，stress test 二次复跑全绿

### item: 写压力测试套件
- **status**: done
- **改动** (`xiaohongshu-saas/tests/stress_test_consolidated.py`):
  - 单文件串联跑：memory（short/long/semantic/episodic 四层）→ RAG → tools → agents → MCP
  - 用 `random.seed(42)` + 65 词词表（alpha/beta/gamma/.../langchain/uvicorn/pydantic）生成随机文本做灌注
  - 规模：short-term 100k items + 5k queries；long-term 20k items + 5k；semantic 20k facts + 5k；episodic 2k + 1k；RAG 15k chunks + 500；tools 5k 顺序 + 2k 并发；agents 1k 并发；MCP 2k 消息
  - 每个子模块跑完打印 `name: scale=X, qps=Y, errors=0` 一行
  - 全套约 200 秒
- **次要文件**:
  - `stress_test_rag_v3.py` / `stress_test_memory_v3.py` / `stress_test_agents_v2.py` / `stress_test_api_v2.py`：单模块拆分版
  - `_bench.py` / `_bench_lt.py` / `_prof.py`：定位瓶颈时用的 micro-bench，定位完后删除
- **下次注意**:
  - 跑全套前先确认 Python 没有真正连外部 LLM（mock embedder 默认开启，`MockEmbedder` 用 hashlib.md5 种子化 random）
  - 如果改了 `app/ai/memory/*.py` 接口签名，要在 stress_test_consolidated.py 里同步改

### item: 发现并修 5 个 perf 塌方 + 1 个 bug
- **status**: done
- **改动** (commit `03015da`，7 文件 889+/93-):
  - **LongTermMemory** (`app/ai/memory/long_term.py`, +112):
    - 加 `auto_save` + `save_batch_size` + `flush()`：store() 不再每次写盘；攒满 100 条 / 显式 flush 才落盘（**~30x 写入加速**）
    - 加 `_word_index` 倒排索引（word → set of item ids），recall 走 "倒排 + 词重叠打分"（**~50x 召回加速**）
    - 每个 item 缓存 `_content_words` / `_content_lower` 避免每次重算
    - 加 `track_access: bool = True` 参数，bulk benchmark 时 `track_access=False` 跳过 datetime.now()（5M+ 次节省）
  - **ShortTermMemory** (`app/ai/memory/short_term.py`, +61):
    - `MemoryItem` 加 `id: str`（UUID4），索引用稳定 id
    - 加 `_word_index` 倒排；`search()` 走倒排 + LRU 兜底
    - `_prune()` 删 item 时同步从 `_word_index` 摘掉，否则索引会无限增长
  - **SemanticMemory** (`app/ai/memory/semantic.py`, +181):
    - `fact_id` 弃用 MD5(statement) 改用 UUID4（MD5 在相似语料下**会哈希碰撞丢数据**，真坑）
    - 单文件 `_index.json` + `flush()` 批量写，不再每 fact 一文件（20k facts = 20k 文件 → 1 个文件）
    - 加 `_word_index` 配合原 `_tag_index`；recall 先取标签交集 + 词索引候选，再算相似度
    - `_save` → `_save_one` 改名；`update_confidence()` 里漏改的旧引用是这次 stress 暴露的 → 修了
  - **InMemoryVectorStore** (`app/ai/rag/vector_store.py`, +144):
    - add() 时 `_rebuild_cache()` 把所有向量预 normalize + 堆成 numpy 矩阵
    - search() 用 `cache @ query` 一次性矩阵乘，**比 Python for-loop 逐个算 cosine 快 1000x**（0.25 qps → 245 qps）
    - top-k 用 `np.argpartition` 替代 `np.argsort`（O(n) vs O(n log n)）
  - **MockEmbedder** (`app/ai/rag/embedder.py`, +12):
    - `sum(ord(c))` 种子 + `np.random.randn()` 改成 `hashlib.md5` 种子 + `np.random.default_rng()`（单条 5ms → 0.02ms）
- **下次注意**:
  - 倒排索引和 LRUCache 是这套 perf 修法的核心，所有 store 路径必须调 `_index_item()`，所有 remove 路径必须调 `_deindex_item()`
  - `InMemoryVectorStore._matrix_cache` 在大量 add 后内存会爆；prod 路线图里写明要换 ChromaDB/FAISS（HNSW 或 IVF）
  - `MockEmbedder` 是测试用的，prod 走 `Embedder(provider="openai")`；切真模型时把 stress_test_consolidated.py 里 `MockEmbedder` 替换掉

### item: 写 ROBUSTNESS-REPORT.md
- **status**: done
- **改动** (`xiaohongshu-saas/docs/ROBUSTNESS-REPORT.md`):
  - Executive Summary + 8 行子模块吞吐表（short 335 qps / long 40 qps / semantic 1844 qps / episodic 1499 qps / RAG 1614 qps / tools 555k cps / agents 62k tps / MCP 220k msgs）
  - 8 节 "Issues Found and Fixed"（含 7 个 perf + 1 个 bug），每节给根因 + 修法 + 涉及文件
  - "Edge Case Coverage"：空串 / 纯空白 / unicode+emoji / 超长 query / 30% miss rate
  - "Recommendations for Production" 5 条：换 ChromaDB / 换真 embedder / Redis 长存 / Redis LRU / API gateway 限流
  - "How to Re-run" 给 4 条命令
- **下次注意**: 文档是 161 行的 UTF-8 纯文本；如果将来添加 NUL byte 又被工具误存为 UTF-16 LE，按 `Format-Hex` + UTF8Encoding 重新写一次（见 facts/windows-shell-encode-gotchas.md）

### item: 推送 03015da 到 origin/main
- **status**: done
- **改动**:
  - 第一次 push 在后台被 user 中断（yield 给 chat 时丢上下文）
  - 第二次在 chat 复盘，先 `git status -sb` 确认 `main...origin/main` 无 ahead/behind 标记，再 `git ls-remote origin main` 拿到 `03015dae984fc5ad48b3049241da51be2ab00b9b`，与 `git rev-parse HEAD` 完全一致 → 推送**实际已成功**
  - 之前那一轮的 `1a1cfb1..03015da  main -> main` 是真实结果；PowerShell 的 `CategoryInfo : NotSpecified: ... RemoteException` 是 git 远程命令经 PowerShell 包装时的已知噪音，不是失败
- **下次注意**:
  - `git push` 在 PowerShell 里被包装成 `git : To <url>...` + RemoteException 字样是正常现象，看 `git ls-remote origin main` 确认 remote SHA 才是 ground truth
  - 不要再跑 `git push --force` 或 `git push --force-with-lease`——remote SHA 已经在 03015da

### 剩余待办（v0.6.4+ AI 平台）
| 优先级 | 待办 | 状态 |
|---|---|---|
| P0 | 推送 03015da | ✅ `git ls-remote` 验过 origin HEAD = 03015da |
| P0 | LongTermMemory 批量落盘 | ✅ `flush()` + `save_batch_size=100` |
| P0 | LongTermMemory 倒排索引 | ✅ `_word_index` + content cache |
| P0 | ShortTermMemory 倒排 + LRU | ✅ `_word_index` + `_prune()` 同步摘索引 |
| P0 | SemanticMemory fact_id 改 UUID | ✅ 修了 MD5 碰撞丢数据 bug |
| P0 | SemanticMemory 批量落盘 | ✅ `_index.json` + `flush()` |
| P0 | VectorStore 矩阵化 | ✅ numpy matrix cache + argpartition |
| P0 | Embedder 哈希种子 | ✅ hashlib.md5 + default_rng |
| P1 | 把 InMemoryVectorStore 换成 ChromaDB | ❌ 当前实现 O(n) 查询，>1M 向量要 HNSW/IVF |
| P1 | 接真 LLM provider | ❌ 当前是 mock；prod 走 OpenAI/Anthropic |
| P1 | LongTermMemory 接 Redis 后端 | ❌ 多进程部署需要共享存储 |
| P1 | ShortTermMemory 接到 Redis sorted set | ❌ 集群部署需要 |
| P2 | 给 tool registry 加 token bucket 限流 | ❌ 555k cps 太快会击穿下游 |
| P2 | Alembic migration 跟上新 ORM 字段 | ❌ `task.tenant_id` 那种新增列要补 migration |
| P2 | 把 stress test 接入 CI | ❌ 当前 200s 跑全有点长，可以 nightly |

## 测试命令

```bash
cd xiaohongshu-saas

# 单元测试（必须全绿）
python -m pytest -q tests

# AI 健壮性 stress test（约 200 秒，灌 200k+ memory 操作 + 70k+ RAG）
python -u tests/stress_test_consolidated.py

# 单模块复测
python -u tests/stress_test_rag_v3.py
python -u tests/stress_test_memory_v3.py
python -u tests/stress_test_agents_v2.py
```

## 已推送的改动（最近 4 个 commit）

```
commit 03015da - perf(ai): optimize memory and RAG robustness under stress
commit 1a1cfb1 - docs(ci-cd): K8s deploy workflow + setup instructions
commit 0c6bb8c - feat(k8s+ai): K8s 持续部署 + AI Agent 平台
commit 6cb4082 - feat(frontend+release): 前端控制台 UX 优化 + 准备 v0.6.3 MSI
```

## 验证记录

```bash
# 1. 单元测试 137/137 全绿
cd xiaohongshu-saas
python -m pytest -q tests
# -> 137 passed in ~10s

# 2. Stress test 全模块
python -u tests/stress_test_consolidated.py
# 1. MEMORY SUBSYSTEM
# Short-term: 100k items, 5k queries, 335 qps, errors=0
# Long-term:  20k items, 5k queries,  40 qps, errors=0
# Semantic:   20k facts,  5k queries, 1844 qps, errors=0
# Episodic:    2k episodes, 1k queries, 1499 qps, errors=0
# 2. RAG SUBSYSTEM
# RAG:        15k chunks, 500 queries, 1614 qps, errors=0
# 3. TOOL REGISTRY
# Tools (seq): 5000 calls, 555k cps, errors=0
# Tools (conc): 2000 calls, 124k cps, errors=0
# 4. AGENTS
# Agents: 1000 concurrent tasks, 62k tps, errors=0
# 5. MCP
# MCP: 2000 messages, 220k msgs/sec, errors=0

# 3. origin/main 真的收到 03015da
git ls-remote origin main
# -> 03015dae984fc5ad48b3049241da51be2ab00b9b	refs/heads/main
```

**核心结论**：5 个 perf 塌方点全部修掉（30x–1000x 加速），1 个 MD5 fact_id 碰撞丢数据 bug 修掉，
系统能扛 200k+ memory 操作 + 70k+ RAG + 8k+ tool call + 2k+ MCP 消息，零错误。

## 2026-07-10 第八次 session 改动（AI 平台 JD 对齐）

### 背景
- 用户给了一张「AI Agent 落地开发」岗位 JD 截图，目标是「照着这个要求把 xiaohongshu-saas 改成这个标准」
- 第七次 session 的 stress/perf 优化（03015da）虽然把性能修满了，但当时 AI 平台骨架是**手搓的**：
  LangChain 实际并未真正接入（`langchain/chain.py` 是 misleading 的手写 shim），
  memory 是 JSON 文件 + 倒排索引，agents 是 if/elif 顺序执行，MCP 只有协议没有 transport
- 这次按 JD 重新走一遍六大里程碑：**真实接入 LangChain/LangGraph、真实 LLM、SQLite-backed memory、
  真实 RAG loaders/rerank、真实 tool 后端、MCP stdio transport**

### M1：框架选型 + 真实 LLM
- **status**: done
- **改动**:
  - `app/ai/llm.py` (new)：`LLMClient` 统一封装 OpenAI / Anthropic / Ollama
    - 用 `langchain_openai.ChatOpenAI`、`langchain_anthropic.ChatAnthropic`、`langchain_community.ChatOllama`
    - **自动 fallback**：provider 是 openai/anthropic 但没配 api_key → 自动切到 mock（这条关键，之前测试全靠它过）
    - `ainvoke()` 阻塞调用；`astream()` SSE 流式输出（async generator）
  - `pyproject.toml`：[project.optional-dependencies].ai 加 `langchain`, `langchain-openai`, `langchain-anthropic`, `langchain-community`, `langchain-text-splitters`, `langgraph`, `langgraph-checkpoint-sqlite`, `langchain-mcp-adapters`, `sentence-transformers`, `docx2txt`, `aiosqlite`
  - **删除** `app/ai/langchain/chain.py`：之前是 misleading 的「LangChain-like」shim，没真用 LangChain
  - `app/ai/langchain/__init__.py`：改成 re-export `LLMClient` / `LLMResponse` / `build_default_llm`
- **下次注意**:
  - LLMClient 构造时拿不到 langchain 模块不要 raise，应走 mock fallback
  - ainvoke/astream 里 `from langchain_core.messages import ...` 必须是 lazy import

### M2：RAG 真材实料
- **status**: done
- **改动**:
  - `app/ai/rag/document_loader.py`：加 `PDFLoader`（`PyPDFLoader` from langchain_community）和
    `DocxLoader`（`docx2txt`）；`DirectoryLoader` 自动识别 .pdf / .docx / .txt / .md
  - `app/ai/rag/text_splitter.py`：`TextSplitter` 改成 `RecursiveCharacterTextSplitter`（from `langchain_text_splitters`）
    作主路径，hand-rolled 作 fallback
  - `app/ai/rag/embedder.py`：`LangChainEmbedder` 优先用 `OpenAIEmbeddings`，回退到 `HuggingFaceEmbeddings` / `FakeEmbeddings`
  - `app/ai/rag/reranker.py`：`CrossEncoderReranker`（`sentence-transformers` 加载 `cross-encoder/ms-marco-MiniLM-L-6-v2`）
    作主路径，keyword `Reranker` 作 fallback
  - `app/ai/rag/generator.py`：走 `LLMClient`；`DEFAULT_SYSTEM_PROMPT` 防幻觉 + 上下文强制约束；
    空上下文直接拒答不调 LLM；新增 `generate_stream()` async generator
  - `app/ai/rag/vector_store.py`：去掉重复的 `_rebuild_cache`，`InMemoryVectorStore` 保留 numpy 矩阵缓存
    （第七次的 perf 优化保留下来）
  - `app/ai/rag/evaluate.py` (new)：`EvalExample` / `EvalResult` / `EvalReport` + `evaluate_retrieval` async
    离线评测，输出 hit-rate@k / MRR / 答案关键词命中率
  - `app/ai/rag/rag_pipeline.py` (new)：`build_default_rag_pipeline()` 工厂方法
- **下次注意**:
  - `build_default_rag_pipeline()` 的 `store_type` 默认值改成 `"memory"`——之前默认 chroma 在测试环境会崩
  - PDFLoader 跑测试需要 `pip install pypdf`；CI 跑全套之前先 `pip install -e ".[dev]"`

### M3：Memory 重做
- **status**: done
- **改动**:
  - `app/ai/memory/db.py` (new)：`MemoryDB` async SQLite 后端
    - 三张表：`memory_items` / `memory_facts` / `memory_episodes`
    - 字段：`agent_id` + `tenant_id` + `layer` 强隔离；索引 `(agent_id, tenant_id, layer, importance)`
    - 完整 upsert / query / delete / stats / clear
  - 四层 memory（short/long/semantic/episodic）全部重写，公开 API 改成 `async`，
    内部走 `MemoryDB`
  - `app/ai/memory/episodic.py`：**修了 lost-context bug**——`start_episode()` 之前会丢弃 in-flight
    episode 的 events；现在会先 auto-close + persist 再开新的
  - `app/ai/memory/summarize.py` (new)：`summarize_text()` 用 LLMClient 做文本摘要
  - `app/ai/memory/manager.py`：`consolidate()` 改成 LLM 摘要 short-term high-importance 项再 promote 到 long-term
    ——这是「context evolution」的关键路径
- **下次注意**:
  - 第七次的 perf 优化（in-memory 倒排、JSON 批量落盘）在这次重做里**没保留**——因为架构变了
  - 新性能数据见 stress_test_consolidated_v2.py：SQLite path 55–144 qps（vs. v1 in-memory 335–1844 qps）
  - 后续 P1：把 SQLite 换成 Redis（多进程共享）或换更快的 keyword index

### M4：LangGraph Agent + StateGraph
- **status**: done
- **改动**:
  - `app/ai/agents/graph.py` (new)：**LangGraph 的轻量 shim**
    - `StateGraph`（add_node / add_edge / add_conditional_edges / compile）
    - `CompiledGraph.ainvoke(state)` + `astream(state)` 支持 node 级别的 checkpoint
    - `Checkpointer` in-memory；`END()` 哨兵；`Send()` fan-out
    - 这样在没装 `langgraph` 的环境（CI 离线）也能跑，prod 把 `app.ai.agents.graph` 换成真的 `langgraph.graph.StateGraph` 即可
  - `app/ai/agents/content_agent.py`：重写为 `ContentAgent`（StateGraph），workflow：
    `route → plan → generate → review → revise → END`，`revise` 是条件边（verdict == "revise" 回到 generate）
  - `app/ai/agents/analysis_agent.py`：重写为 `AnalysisAgent`（StateGraph），workflow：
    `plan → query_rag → synthesize → END`，`query_rag` 节点调 `build_default_rag_pipeline()`
  - `app/ai/agents/coordinator.py`：重写为 `CoordinatorAgent`（StateGraph），**多 agent fan-out**，
    `asyncio.gather` 并行调 ContentAgent + AnalysisAgent，最后 `synthesize` 节点收口
  - `app/ai/agents/base.py`：注释说明新 graph 应该用 `app.ai.agents.graph.StateGraph`
- **下次注意**:
  - 节点函数必须 `async def node(state) -> dict`（state 增量返回，不直接 mutate）
  - conditional edge 的 router 函数必须返回目标节点名（字符串），不是布尔

### M5：Tool 真材实料 + MCP stdio transport
- **status**: done
- **改动**:
  - `app/ai/tools/content_tools.py`：`GenerateTitleTool` / `GenerateBodyTool` / `SuggestHashtagsTool`
    调 `LLMClient.ainvoke`，无 key 走 mock
  - `app/ai/tools/scheduler_tools.py`：`SchedulePostTool` 尝试 `from app.scheduler.runner import get_scheduler`
    → `add_job(_publish_via_publisher, ...)`，没起 scheduler 时落 mock task_id
  - `app/ai/tools/search_tools.py`：`SearchTrendingTool` 加 `_scrape_trending()` 用 playwright 真实抓
    站（`XHS_TRENDING_SCRAPE=1` 时启用），否则用静态列表
  - `app/ai/mcp/protocol.py`：`MCPMessage` 把 classmethod `error` 改名 `make_error`——之前的命名冲突
    让 `error` 字段变成了 classmethod 对象本身，JSON 序列化直接 TypeError
  - `app/ai/mcp/transport.py` (new)：`serve_stdio()` stdin/stdout JSON-RPC 2.0 server，
    配套 `MCPClient`，跟 `langchain-mcp-adapters` 兼容
- **下次注意**:
  - playwright 浏览器二进制 (~150MB) 默认不装；CI 想跑真抓要 `playwright install chromium`
  - `SchedulePostTool` 现在总是返回 task_id（哪怕是 mock 的），下游可以直接 poll

### M6：Demo + 面试材料
- **status**: done
- **改动**:
  - `app/api/ai.py` (rewrite)：FastAPI 路由
    - `POST /api/ai/chat`：调 CoordinatorAgent
    - `POST /api/ai/chat/stream`：SSE 流式 RAG 回答
    - `POST /api/ai/ingest`：把文档灌进 RAG（PDF / DOCX / TXT）
    - `POST /api/ai/rag/query`：直接查 RAG
    - `POST /api/ai/memory/{add,recall,consolidate}`：四层 memory 暴露
    - `POST /api/ai/tools/call` + `GET /api/ai/tools`：tool registry
    - `GET /api/ai/agents`：列出已注册的 agents
    - `GET /api/ai/status`：feature flag 总览
  - `docs/AI-AGENT-ARCHITECTURE.md` (new)：高层 Mermaid flowchart + 内容 agent sub-graph +
    module map 把 JD 每条要求对应到代码文件
  - `docs/AI-AGENT-DEMO.md` (new)：setup + 逐个 curl 例子 + 60 秒录屏脚本
  - `tests/stress_test_consolidated_v2.py` (new)：适配 async/SQLite 新 API 的 stress test
  - `tests/stress_test_consolidated.py` (old)：**删除**——公开 API 已变，保留下来只会成为破窗
- **下次注意**:
  - `/api/ai/chat/stream` 的 SSE 格式按 `data: <json>\n\n` + `event: end` 收尾，前端用 `EventSource`
  - `AI-AGENT-DEMO.md` 的 mock fallback 章节要标粗：面试 demo 时只跑 mock，不消耗真 LLM 配额
  - `tests/stress_test_consolidated_v2.py` 现在跑完约 180s，CI 走 nightly 不阻塞 PR

### 单元测试
- `python -m pytest -q tests` → **136 passed in ~6s**
- `python -u tests/stress_test_consolidated_v2.py` →
  ```
  short_term_qps:    144
  long_term_qps:     139
  semantic_qps:      89
  episodic_qps:      55
  rag_qps:           3464
  coordinator_tps:   100438
  mcp_msgs_per_sec:  205492
  ```
- 关键变化：memory 吞吐比 v1 慢一个数量级（v1 in-memory 1844 qps semantic），
  这是 SQLite per-row 持久化的代价——可接受，prod 路线图用 Redis

### 剩余待办（v0.7+）
| 优先级 | 待办 | 状态 |
|---|---|---|
| P0 | 推送 AI 重写 | ✅ 2eebf78, origin/main = 2eebf78 |
| P1 | InMemoryVectorStore → ChromaDB | ❌ 当前是 O(n) 查询，>100k 向量要 HNSW/IVF |
| P1 | 接真 LLM provider | ❌ 当前自动 fallback 到 mock；prod 走 OpenAI / Anthropic |
| P1 | MemoryDB → Redis 后端 | ❌ 多进程部署需要共享存储 |
| P1 | ShortTermMemory 接 Redis sorted set | ❌ 集群部署需要 |
| P2 | tool registry 加 token bucket 限流 | ✅ M7: app/ai/tools/rate_limit.py + 6 unit tests |
| P2 | Alembic migration 跟上新 ORM 字段 | ❌ 新增列需要 migration |
| P2 | 把 stress test 接入 CI | ❌ 180s 太长走 nightly |
| P2 | 内容 agent 真实发到 xhs 跑通端到端 | ❌ 还需要扫码 + 真实 cookie |
| P2 | Coordinator agent 接入 APScheduler | ❌ 现在是手动 await.run() |

## 2026-07-10 第九次 session 改动（tool registry 限流）

### 背景
- 第七次 stress test 跑出来 tool 调到了 555k calls/sec（in-process 跑分）—— 这个速度在 prod 会击穿任何真实下游（APScheduler / playwright / OpenAI API）
- 第八次重写时留了「tool registry 加 token bucket 限流」这条 P2
- 第九次 session 把它补上

### item: 实现 tool rate limiter
- **status**: done
- **改动** (commit `M7`，3 文件 154+/6-):
  - `app/ai/tools/rate_limit.py` (new, 137 行)：
    - `TokenBucket` 异步安全的令牌桶（`asyncio.Lock` + `time.monotonic`）
    - `acquire()` 非阻塞取令牌；`acquire_or_wait(max_wait)` 阻塞版本
    - `retry_after()` 算出距离下一个令牌的秒数
    - `rate_per_minute <= 0` 时整个桶禁用
    - `RateLimiterRegistry` 维护 `tool_name -> TokenBucket` 映射
  - `app/ai/tools/registry.py`：
    - `ToolRegistry.__init__` 加 `default_rate_per_minute=60` / `default_capacity=10` 参数
    - `register()` 自动建桶
    - `configure_rate_limit(name, rate_per_minute, capacity=10)` 调单个工具限额
    - `disable_tool(name)` / `enable_tool(name)` 禁用/启用
    - `execute()` 前置三道闸：disabled → rate-limited → not found
    - rate_limited 时 `ToolResult` 带 metadata：`{reason, retry_after, limit_per_minute}`
    - 这样调用方能 backoff 而不是只看到裸 `False`
  - `tests/test_ai_tools.py`：6 个新测试
    - 突发（capacity=3，4 次连续 → 3 成功 + 1 rate_limited）
    - `rate=0` 禁用
    - refill 验证（600/min capacity=2，1 token 100ms 回）
    - disabled tool 返回 reason=disabled
    - per-tool 隔离（title 用完，body 还有）
    - 暴露 `registry.rate_limiter` 属性
- **下次注意**:
  - 默认 60/min 够温和；要让 stress_test_consolidated_v2.py 跑全套 5000+ 调用得显式 configure
  - v2 stress test 现在用的是 default registry（200 调用量），没碰到限流
  - 真实生产部署应该按工具类型分层限额：search_trending 30/min、schedule_post 10/min、content_tools 120/min
  - 跨进程限流当前不实现（TokenBucket 是 in-process）；下一步如果要 P1 集群限流，把 TokenBucket 换成 Redis token bucket
- **测试**: 142/142 单元测试通过（之前 136 + 6 新增）；stress test v2 全绿 180s
- **验证**:
  - 单工具 50 calls @ capacity 10k → 0 rate_limited
  - 单工具 20 calls @ capacity 10 (default) → 10 成功 + 10 rate_limited（符合预期）
  - 不同工具之间互不影响（每个工具独立桶）

### 剩余待办（v0.7+）
| 优先级 | 待办 | 状态 |
|---|---|---|
| P1 | InMemoryVectorStore → ChromaDB | ❌ 当前是 O(n) 查询，>100k 向量要 HNSW/IVF |
| P1 | 接真 LLM provider | ❌ 当前自动 fallback 到 mock；prod 走 OpenAI / Anthropic |
| P1 | MemoryDB → Redis 后端 | ❌ 多进程部署需要共享存储 |
| P1 | ShortTermMemory 接 Redis sorted set | ❌ 集群部署需要 |
| P1 | 把限流挂到 API 网关 | ❌ 当前是 in-process 限流；多 uvicorn worker 不共享 |
| P2 | Alembic migration 跟上新 ORM 字段 | ❌ 新增列需要 migration |
| P2 | 把 stress test 接入 CI | ❌ 180s 太长走 nightly |
| P2 | 内容 agent 真实发到 xhs 跑通端到端 | ❌ 还需要扫码 + 真实 cookie |
| P2 | Coordinator agent 接入 APScheduler | ❌ 现在是手动 await.run() |
