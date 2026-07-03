# auto-fix-tests.sh / auto-fix-tests-npm.sh

> 自动让 Claude agent 修失败的测试，套娃式 loop 直到绿 / 烧光预算。

## 两个语言各一份

| 脚本 | 默认测试命令 | 适用项目 |
|---|---|---|
| `scripts/auto-fix-tests.sh` | `pytest -q` | Python（xiaohongshu-saas 等） |
| `scripts/auto-fix-tests-npm.sh` | `npm test --silent` | Node.js / 前端 |

两份脚本结构完全对称，只是默认值不同。内部逻辑（loop / 预算 / prompt 约束）共用同一套设计。

## 一句话定位

CI 红了 → 让 agent 自愈，最小改动，不弱化测试，不碰无关代码。

## 为什么需要这个

半夜 CI 红了 1-2 处，但你已经躺平。让一个无状态的 agent loop 自动修，醒来发现要么绿了、要么人类确实得接手。

## 三层防线

| 层 | 机制 | 防什么 |
|---|---|---|
| 1 | `set -euo pipefail` | 脚本静默失败 / 未定义变量 / 管道掩盖错误 |
| 2 | `MAX_ITER=10` | 无限循环 / 单次会话烧太多钱 |
| 3 | `--max-budget-usd 5` | 单轮 token 失控 |

## 核心设计

### 1. Check first, fix second

```bash
if pytest -q; then exit 0; fi   # 已绿就别调 agent
claude -p "..."                  # 只在真红了才烧钱
```

这避免了 `i=0` 时调用 agent 浪费一轮（很多 CI 一上来就绿）。

### 2. 三条 prompt 约束

agent prompt 里硬编码三条规则：

```
make the smallest fix        → 防止 agent 看到测试红就重构整个模块
Do not touch unrelated code  → 防止顺手改 lint / 风格 / README
Do not weaken tests          → 防止 agent 用 skip / mock / delete 让测试假绿
```

**第三条最重要**——没有它，agent 会很快发现"删掉失败测试"是最便宜的胜利。

### 3. `--permission-mode acceptEdits`

脚本无人值守，agent 任何写入权限弹窗都会卡死直到超时。`acceptEdits` 让 agent 能改文件但**不会**：
- 执行任意 shell 命令（除非另有授权）
- 删除文件
- 改 git 配置

### 4. agent 失败时 continue

```bash
if ! claude -p "..." --max-budget-usd "$BUDGET"; then
  echo "claude agent failed at iteration $i, continuing"
fi
```

没有这个 `if ! ... then ... fi`，`set -e` 会在 `claude -p` 因网络 / 预算失败时直接终止整个 loop，浪费剩下 N-1 轮的预算。

## 用法

### 默认参数（pytest 版）

```bash
bash scripts/auto-fix-tests.sh
# 等价于: MAX_ITER=10 BUDGET=5 TEST_CMD="pytest -q"
```

### 默认参数（npm 版）

```bash
bash scripts/auto-fix-tests-npm.sh
# 等价于: MAX_ITER=10 BUDGET=5 TEST_CMD="npm test --silent -- --watchAll=false"
# 脚本会额外 export CI=1, 让 jest/vitest/cypress/playwright 拒绝 watch 模式。
```

### npm watch 模式陷阱

npm 测试常自带 watch 模式（`jest --watchAll`、`vitest --watch`、Cypress 的 `run --watch`），默认会等 stdin 永远不退出——**外层 loop 会在第二轮卡死**。脚本做了两件事防这个：

1. **强制 `export CI=1`** — jest/vitest/cypress/playwright 全认这个环境变量，会自动拒绝 watch
2. **默认 `TEST_CMD` 透传 `--watchAll=false`** — 双保险，关掉 jest 残余 watch

用户自定义 `TEST_CMD` 时无需再加 `CI=1` 前缀（脚本已 export）。

### 自定义轮数 / 预算

```bash
MAX_ITER=20 BUDGET=10 bash scripts/auto-fix-tests.sh
MAX_ITER=20 BUDGET=10 bash scripts/auto-fix-tests-npm.sh
```

### 跑别的测试命令

```bash
# Python 跑特定子目录
TEST_CMD="pytest -q xiaohongshu-saas/tests" bash scripts/auto-fix-tests.sh

# npm 跑特定子项目 (CI=1 已由脚本 export, 无需重复)
TEST_CMD="npm test --silent -- --watchAll=false --testPathPattern=core" bash scripts/auto-fix-tests-npm.sh

# 其他生态 (CI=1 不影响这些, pytest/cargo/go 没 watch 模式)
TEST_CMD="cargo test --quiet" bash scripts/auto-fix-tests.sh
TEST_CMD="go test ./..." bash scripts/auto-fix-tests.sh

# pnpm / yarn — 透传 watchAll=false 即可
TEST_CMD="pnpm test --silent -- --watchAll=false" bash scripts/auto-fix-tests-npm.sh
TEST_CMD="yarn test --silent --watchAll=false" bash scripts/auto-fix-tests-npm.sh
```

### npm 版 prompt 的微小差别

npm 版第三条约束写成 `no skip / .skip() / xit / delete`——多列 `.skip()` 和 `xit`（Jest 常用别名），更精确地封死"假绿"路径。pytest 版则是 `no skip / mock / delete`。

## 实际跑起来长这样

```
auto-fix-tests: TEST_CMD='pytest -q' MAX_ITER=10 BUDGET=$5

=== iteration 1 / 10 ===
FAILED xiaohongshu-saas/tests/test_risk.py::test_sla_window - AssertionError
claude: edited xiaohongshu-saas/app/core/risk.py (1 line)

=== iteration 2 / 10 ===
5 passed in 0.42s
Green in 2 iterations.
```

通常 **1-3 轮能搞定**；超过 5 轮基本说明问题不是修测试能解决的（架构 / 依赖版本 / 环境），这时候让人类接手。

## 适用 / 不适用

| ✅ 适合 | ❌ 不适合 |
|---|---|
| 套件里有 1-2 个明确失败，agent 能定向修 | 架构性失败（设计问题，code 改完仍 fail） |
| 失败的根因明确、定位到文件 / 行 | 测试本身有 bug（按"不弱化测试"规则会卡住） |
| 你信任 agent 的 diff 质量 | 跨多包 monorepo（默认 `pytest -q` 跑全套太慢） |
| 凌晨 / 周末想睡个安稳觉 | 涉及数据库迁移 / 网络 IO 的集成测试 |

## 风险与边界

- **agent 改错怎么办？** 整个仓库是 git tracked，任何时候 `git diff` 能看到每一轮的改动。不放心可以加 `--dry-run` 或要求 agent 把 diff 先 print 再写。
- **网络断了怎么办？** `claude -p` 失败会被 `if !` 捕获，循环继续；预算耗尽也一样。
- **agent 陷入循环怎么办？** `MAX_ITER=10` 硬上限，第 10 轮仍红就退出 1，CI 会 fail。
- **会不会改到无关代码？** prompt 里硬约束 `Do not touch unrelated code`，但 agent 不是 100% 守规矩——定期 review diff 仍是必要的。

## 扩展建议

### 加 dry-run 模式

```bash
# 只打印 plan 不真的改文件
DRY_RUN=1 bash scripts/auto-fix-tests.sh
```

需要改脚本加：

```bash
if [ "${DRY_RUN:-0}" = "1" ]; then
  CLAUDE_FLAGS="--permission-mode plan"
else
  CLAUDE_FLAGS="--permission-mode acceptEdits"
fi
```

### 接 CI

仓库根已带 **`.github/workflows/auto-fix.yml`**，对接的是 `xhs-saas-ci.yml`：

| 行为 | 描述 |
|---|---|
| 触发 | 订阅 `xhs-saas-ci` 的 `workflow_run` 完成事件 |
| 触发条件 | 仅当上游 CI `conclusion == 'failure'` |
| 工作内容 | checkout → 装依赖 → 跑 `scripts/auto-fix-tests.sh` → 校验 diff → push 到 main → 等二次 CI → 必要时 revert |
| 超时 | 30 分钟（10 轮 agent × 3 分钟 worst case） |

#### 五层纵深防御

```yaml
# .github/workflows/auto-fix.yml (节选)
- paths 过滤:  agent 只能改 xiaohongshu-saas/**
- diff size:    超过 1000 行放弃 push
- 二次 CI:      push 后自动再跑 xhs-saas-ci, 失败则自动 revert
- concurrency:  同一分支串行化, 防止两次 auto-fix 互相覆盖
- infinite-loop guard: 检测 HEAD commit 消息含 "auto-fix", 跳过
```

#### 必需的 GitHub 配置

在仓库 settings → secrets and variables → actions 里加：

```
ANTHROPIC_API_KEY = <your-key>
```

仓库 settings → branches → main 建议启用：

- **Require status checks** — `xhs-saas-ci` 必须过
- **Do not allow bypassing the above settings** — 包括管理员
- **Allow specified actors to bypass** — 留空（auto-fix 也走 `GITHUB_TOKEN` 推）

#### 触发闭环流程

```
PR merge → xhs-saas-ci runs → CI fails
                ↓
        workflow_run 触发 auto-fix
                ↓
   ┌─ 10 轮: read fail → minimal fix → pytest
   │         ↓
   │   green? → 二次 CI → green ✓ → push to main
   │                   └─ red ✗ → auto revert
   │   red?  → 放弃 (push 取消), 留 main 干净
   └─ budget 烧光 → 放弃, 留 main 干净
```

#### 触发流程外的紧急停止

如果 auto-fix 失控（agent 反复尝试改同一文件）：

```bash
# 1. 关掉 workflow 文件触发 (不删文件)
#    在 .github/workflows/auto-fix.yml 加:
on: workflow_run: { workflows: ["xhs-saas-ci"] }  # 注释掉整个 on 块

# 2. 或在 GitHub Actions UI 选 cancel workflow run

# 3. 或 push 一个无关 commit, HEAD 就不是 auto-fix 相关, 打破循环检测
```

#### 跨 monorepo 适配

`auto-fix.yml` 现在只对接 `xhs-saas-ci`。要扩展到其他子项目：

```yaml
# 1. 复制 auto-fix.yml → auto-fix-pbp.yml
# 2. 改 workflow_run.workflows = ["pbp-ci"]
# 3. 改 paths 过滤到对应子项目
# 4. 改 secret 名 (如 ANTHROPIC_API_KEY_PBP)
```

#### 早期版本 (一段骨架)

> 警告：以下骨架没有纵深防御，agent 改完直接 push 没有二次验证。

```yaml
on:
  workflow_run:
    workflows: ["CI"]
    types: [completed]
jobs:
  fix:
    if: ${{ github.event.workflow_run.conclusion == 'failure' }}
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install claude-code
      - run: bash scripts/auto-fix-tests.sh
      - run: git push  # 直接 push, 无二次验证
```

仓库里的 `auto-fix.yml` **不是**这个骨架——它有完整 5 层防御。

## 相关文件

- 脚本本体: `scripts/auto-fix-tests.sh`（Python / pytest）
- 脚本本体: `scripts/auto-fix-tests-npm.sh`（Node.js / npm）
- CI 集成: `.github/workflows/auto-fix.yml`（订阅 xhs-saas-ci）
- 灵感来源: Anthropic 内部 ralph-loop 模式