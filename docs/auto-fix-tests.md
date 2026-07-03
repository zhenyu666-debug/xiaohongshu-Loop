# auto-fix-tests.sh

> 自动让 Claude agent 修失败的测试，套娃式 loop 直到绿 / 烧光预算。

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

### 默认参数

```bash
bash scripts/auto-fix-tests.sh
# 等价于: MAX_ITER=10 BUDGET=5 TEST_CMD="pytest -q"
```

### 自定义轮数 / 预算

```bash
MAX_ITER=20 BUDGET=10 bash scripts/auto-fix-tests.sh
```

### 跑别的测试命令

```bash
# npm 项目
TEST_CMD="npm test --silent" bash scripts/auto-fix-tests.sh

# 跑特定子目录
TEST_CMD="pytest -q xiaohongshu-saas/tests" bash scripts/auto-fix-tests.sh

# cargo
TEST_CMD="cargo test --quiet" bash scripts/auto-fix-tests.sh
```

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

```yaml
# .github/workflows/auto-fix.yml
name: auto-fix-tests
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
      - run: git push  # 如果 agent 改了什么，自动推回
```

> 警告：自动 push 可能引入 agent 误改，建议先把 agent 的改动做成 PR 而不是直接 push。

## 相关文件

- 脚本本体: `scripts/auto-fix-tests.sh`
- 灵感来源: Anthropic 内部 ralph-loop 模式