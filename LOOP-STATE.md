# LOOP-STATE.md

> Agent loop 跑前**先读这个文件**——避免重做已完成的事。
> 每次 item 完成后更新本文件。
>
> **命名约定**：本仓库本文件叫 `LOOP-STATE.md`（不带 `xhs` 后缀）。
> 旧的 `LOOP-STATExhs.md` 是上一个 session 的工作日志，保留作为历史档案，**不是 loop 状态源**。

Last updated: 2026-07-03 22:03 UTC+8 (本次 run)
Session: loop boot 第四轮 — 修 auto-fix.yml pytest cwd 错乱

## 验证证据 (item 完成必须基于此)

- HEAD SHA: `91a166df805f0ce52bdd435b889264cf6fbc1f5d` (`main`)
- 远端 SHA: 同上（已同步）
- 本 session 推到 main 的 commits: `c453420` + `9854e11` + `c6165af` + `2c75ceb` + `080d803` + `91a166d` (cwd 错乱 fix)
- 关键发现:
  - **item 6 (commit 080d803)**: auto-fix.yml diff size 漏算 deletion, 改用 --numstat 累加 ins+del
  - **item 7 (commit 91a166d)**: auto-fix.yml Run auto-fix loop step 没设 cwd, pytest 找不到 tests/ 卡死
- 工作区状态: 7 个未跟踪 .py 临时脚本（见 item 3）
- 主分支 commits: 见 `git log --oneline -20`
- 工作区状态: 7 个未跟踪 .py 临时脚本（见 item 3）
- 旧的 `LOOP-STATExhs.md` line 118-134 列的"未 push 改动" 8/10 实际**已在 HEAD**（早在 `7e78510` 初始 commit 一次性带上），仅 2/10（demo.json + demo_*.jpg）被 `xiaohongshu-saas/.gitignore` 的 `data/` 规则挡住从未进 git。

## Item 列表

### item 1: 验证 LOOP-STATExhs.md 未 push 清单实际状态
- **status**: done
- **做了什么**:
  - 8/10 文件 `git log -- <path>` 显示早已在 `7e78510` / `1229d20` / `19243ef` 等历史 commit
  - 仅 `xiaohongshu-saas/data/templates/demo.json` 和 `xiaohongshu-saas/data/images/demo_*.jpg` 从未进 git
  - `git check-ignore` 确认被 `xiaohongshu-saas/.gitignore:16` 的 `data/` 规则忽略
- **下次注意**:
  - `LOOP-STATExhs.md` 是上一个 session 的工作日志，**不是 current state**——下次别再当 item 源
  - `LOOP-STATExhs.md` line 132 的 git 命令是"计划"，**没被执行过**——别相信这个清单

### item 2: 建 LOOP-STATE.md（让 loop 真正有 state 源）
- **status**: done
- **做了什么**:
  - 新建本文件 `LOOP-STATE.md`（不带 `xhs` 后缀）
  - 把 item 1 的 evidence 固化到 "验证证据" 段
  - 旧的 `LOOP-STATExhs.md` 保留作为历史档案
- **下次注意**:
  - 任何"未完成的事"必须进 item list，不能只留在 `LOOP-STATExhs.md`
  - 每次 run 开始**先读本文件**

### item 3: 检查 7 个未跟踪 .py 文件
- **status**: blocked → needs me
- **做了什么**:
  - 读每个文件前 30-280 行，分类如下
- **分类**:
  - **`check_*.py` (4 个, < 600B)**: 临时调试脚本，**硬编码**仓库外的路径 (`db/getjobs.db`)，无业务价值
    - `check_cookie.py` 545B — sqlite 查 cookie 表
    - `check_db.py` 237B — sqlite 列所有表名
    - `check_encoding.py` 303B — 读 Java 路径，**Java get-jobs 残留**
    - `check_img.py` 332B — PIL 读外部 Cursor projects 路径
  - **`qcc_scraper_*.py` (3 个, 8-17KB)**: 完整企查查爬虫，**三种实现**（http / playwright / standalone），含硬编码反爬 headers
- **现状**:
  - 这些**没**被 `.gitignore` ignore（只有 `_check_*.py` 在 ignore 列表）
  - 仓库 `scripts/` 目录**没有 .py**——根 .py 全是临时
  - `qcc/` 整个目录被 `.gitignore` ignore——`qcc_scraper_*.py` 应该**归到 qcc/** 下，不 commit
- **建议决策** (NEEDS ME, 见 needs-me list):
  - (A) **trash 全部 7 个** — 临时调试 + qcc scraper 都不该在仓库根
  - (B) **trash 4 个 check_*.py**，**mv 3 个 qcc_scraper 到 qcc/**（被 ignore，不 commit）
  - (C) **trash 全部**，理由：qcc scraper 和 xiaohongshu-saas 项目无关
- **下次注意**:
  - 任何 `rm` / `trash` / `mv` 都是 destructive → needs me
  - 仓库根 .py 是 100% 临时——以后再有 .py 应该直接归到合适目录

### item 4: data/templates/demo.json + data/images/demo_*.jpg 是否应该 push
- **status**: needs me
- **现状**:
  - 文件存在 working tree，未进 git
  - 被 `xiaohongshu-saas/.gitignore:16` 的 `data/` 规则挡
  - `data/cookies/` 也在 data/ 下，但**绝对不能 push**（私有 cookie）
  - `data/xhs_saas.db`（sqlite DB）也在 data/ 下，**通常也不该 push**
- **decision needed**:
  - (A) 改 `.gitignore` 改成只 ignore `data/cookies/` `data/*.db` 不 ignore `data/templates/` `data/images/`，然后 force-add demo 文件
  - (B) 维持现状，demo 数据**只本地用**（要求用户每次自己 `python -m scripts.seed_demo`）
  - (C) 删掉这些本地 demo 文件（用户可能不想用 demo）
- **风险**: 改 `.gitignore` + force-add 之前被故意 ignore 的文件 = "destructive / pushing things" → needs me

### item 5: 跑 pytest -q tests 看真实测试状态（evidence-based 探索）
- **status**: done
- **做了什么**:
  - `cd xiaohongshu-saas && python -m pytest -q tests`
  - 不需要 `pip install -e ".[dev]"`（pytest 9.1.0 系统已装, 其他依赖 import 时才校验）
- **结果**:
  - `rc=0`, `22 passed in 2.16s`
  - 测试目录 5 个文件: `test_douyin_stub.py`, `test_factory.py`, `test_metrics.py`, `test_risk.py`, `test_schemas.py`
- **含义**:
  - **CI 绿的（本地环境）** → auto-fix workflow 现在没有触发理由，**当下没必要跑**
  - 本地绿 ≠ GitHub Actions CI 绿（环境变量, secret, OS 可能不同）
  - 真正的 CI 是否绿要看 `https://github.com/zhenyu666-debug/xiaohongshu-Loop/actions`
- **下次注意**:
  - 调试入口: `cd xiaohongshu-saas && python -m pytest tests/test_<name>.py -v`
  - 加新测试要"Match the patterns" (`test_*.py` 函数名 `test_*`)

### item 6: 修 auto-fix.yml diff size 漏算 deletion 的 bug
- **status**: done
- **做了什么**:
  - 阅读 `.github/workflows/auto-fix.yml`, 发现 line 124-129 的 DIFF_LINES 只 grep `[0-9]+ insertion`
  - 改用 `git diff --cached --numstat | awk '{ins+=$1; del+=$2} END {print ins+del+0}'`
  - 在 tempdir 跑 git init + bash 验证 4 个 case
- **结果** (用 Git Bash awk 测真实 git):
  - insert 1 line: 1 ✓
  - delete 1 line: 1 (老代码 0) ✓
  - no changes: 0 ✓
  - 1499 line 删除: 1501 (老代码 0) ✓ — 老代码 silently 放行
- **Commit**: `080d8031e4ef2c7a58577e2a01a29dafc7348a4a` on main
- **下次注意**:
  - 老 grep 是"writing-dominant"假设, 真实场景 deletion 是 silent attack vector
  - 任何"基于 --stat 的统计限制"应该用 --numstat + awk 累加, 或 `git diff --shortstat` 的数字
  - Git Bash 在 `C:/Program Files/Git/bin/bash.exe` 下调用 awk 有效 (系统 `bash.exe` 是 WSL, 没 awk)

### item 7: 修 auto-fix.yml Run auto-fix loop step 缺 working-directory
- **status**: done
- **做了什么**:
  - 发现 `Run auto-fix loop` step (line 89-100) 没设 `working-directory`, 默认仓库根
  - `TEST_CMD="pytest -q tests"` 在仓库根跑: pytest 找不到 tests/, 卡在 rootdir detection 30s timeout
  - 设计 fix: Run auto-fix loop 切到 xiaohongshu-saas/, 后续 git 操作 step 切回仓库根
- **结果** (tempdir 模拟):
  - `pytest -q tests` 仓库根: ERROR file not found, rc=4 ❌
  - `pytest -q tests` xiaohongshu-saas: 22 passed ✓
  - `git diff :!xiaohongshu-saas` 仓库根: 排除正确 ✓
  - `git diff :!xiaohongshu-saas` 子目录 cwd: 排除失效 ⚠️ (path 相对 cwd 解释)
- **改动**: 6 处 working-directory, 1 处 git add path 限定
  - `Run auto-fix loop`: `working-directory: xiaohongshu-saas`
  - `Inspect agent diff`, `Push agent fix`, `Trigger CI re-verification`, `Wait + verify CI re-run`, `Revert agent fix`: `working-directory: .`
  - `git add -A` → `git add -A xiaohongshu-saas` (保险)
- **Commit**: `91a166df805f0ce52bdd435b889264cf6fbc1f5d` on main
- **下次注意**:
  - GitHub Actions step 级 cwd 互不影响, 每个 step 自己设
  - 任何 step 跑测试 / 跑 build 都必须显式设 cwd, 不能假设继承
  - `git diff :!path` 是 repo-root 相对 path, 子目录 cwd 下会错

## Needs-me list（agent 没法决定的事）

### ~~item 3 + repro_test.sh: 8 个未跟踪垃圾文件~~ → ✅ DONE (用户"quanbu" 拍板: 全部)
- **2026-07-04 02:35 UTC+8** 用户命令"quanbu"=全部, agent 全部 trash 到 Windows Recycle Bin
- 实现: custom helper `_SendTo-RecycleBin.ps1` 用 `[Microsoft.VisualBasic.FileIO.FileSystem]::DeleteFile(..., SendToRecycleBin)`
- 验证: 8 个文件全 `exists=False`, 8 个全在 Recycle Bin (30 天可恢复)
- 操作清单:
  - check_cookie.py, check_db.py, check_encoding.py, check_img.py
  - qcc_scraper_http.py, qcc_scraper_pw.py, qcc_scraper_standalone.py
  - repro_test.sh

### 仍然 pending:

1. **demo.json + demo_*.jpg 是否 push** (item 4)
   - (A) 改 .gitignore 精细化 + force-add
   - (B) 维持现状，本地 demo 模式
   - (C) 删掉本地 demo 文件

2. **`_SendTo-RecycleBin.ps1` 去留** (新)
   - 是 trash 8 个文件用的 PowerShell helper (没 `trash` CLI 时替代方案)
   - 现在仓库根 untracked
   - 选项:
     - (a) **mv 到 `scripts/`** + 改名 `trash.ps1` — 工具化, match `scripts/` 已有 pattern (推荐)
     - (b) **trash 进回收站** — 用一次就丢
     - (c) **commit 进 repo** — 文档化为 agent 工具

## 测试命令（参考 `LOOP-STATExhs.md` line 88-116）

```bash
cd xiaohongshu-saas
python -m pytest -q tests
```

## 下次 run 提示

1. 读本文件 `LOOP-STATE.md` first
2. 检查 HEAD SHA 和本文件记录的 SHA 一致 → 没人偷偷 push
   - **注意**: LOOP-STATE.md 改一次 → commit 一次 → HEAD 变一次 → 段本身过时
   - **本文件证据段只反映最近一次 commit 前的状态**; 完整 git log 在 `git log --oneline -20`
3. 看 item 列表，挑 `pending` 的干，跳过 `done` 和 `needs me`
4. 每次完成 item 立即回写本文件
5. **没 GOAL 的 loop 不会自动跑** — 用户给了空的 loop 模板让我自由探索，agent 已尽力做完能做的 evidence 验证，剩下的 decision-requiring 全归 needs-me
