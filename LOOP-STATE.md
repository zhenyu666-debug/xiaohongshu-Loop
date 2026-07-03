# LOOP-STATE.md

> Agent loop 跑前**先读这个文件**——避免重做已完成的事。
> 每次 item 完成后更新本文件。
>
> **命名约定**：本仓库本文件叫 `LOOP-STATE.md`（不带 `xhs` 后缀）。
> 旧的 `LOOP-STATExhs.md` 是上一个 session 的工作日志，保留作为历史档案，**不是 loop 状态源**。

Last updated: 2026-07-03 20:54 UTC+8
Session: loop boot — 验证 LOOP-STATExhs.md 残留清单

## 验证证据 (item 完成必须基于此)

- HEAD SHA: `333bb11958491de447fa1986b9f0a48d22021623` (`main`)
- 远端 SHA: 同上（已同步）
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

## Needs-me list（agent 没法决定的事）

1. **7 个未跟踪 .py 文件去留** (item 3) — `check_*.py` (4) + `qcc_scraper_*.py` (3)
   - 建议 trash 4 个 check_*（临时调试，硬编码仓库外路径）
   - 建议 mv 3 个 qcc_scraper 到 qcc/（被 .gitignore ignore，不 commit）
   - 或全部 trash
   - **任何 `rm` / `trash` / `mv` 是 destructive → 需用户拍板**

2. **demo.json + demo_*.jpg 是否 push** (item 4) — 见 item 4 decision matrix
   - (A) 改 .gitignore 精细化 + force-add
   - (B) 维持现状，本地 demo 模式
   - (C) 删掉本地 demo 文件

## 测试命令（参考 `LOOP-STATExhs.md` line 88-116）

```bash
cd xiaohongshu-saas
python -m pytest -q tests
```

## 下次 run 提示

1. 读本文件 `LOOP-STATE.md` first
2. 检查 HEAD SHA 和本文件记录的 SHA 一致 → 没人偷偷 push
3. 看 item 列表，挑 `pending` 的干，跳过 `done` 和 `needs me`
4. 每次完成 item 立即回写本文件
5. **没 GOAL 的 loop 不会自动跑** — 用户给了空的 loop 模板让我自由探索，agent 已尽力做完能做的 evidence 验证，剩下的 decision-requiring 全归 needs-me
