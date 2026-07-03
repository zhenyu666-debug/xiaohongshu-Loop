#!/usr/bin/env bash
# auto-fix-tests.sh — 自动让 agent 修失败的测试
#
# 思路: CI 红了 → 让 Claude agent 自动读失败 → 做最小修复 → 再跑 → 直到绿 / 烧光预算
#
# 设计要点:
#   1. "check first, fix second" — 已绿就别调 agent, 避免浪费一轮预算
#   2. agent prompt 三条约束: 最小改动 / 不碰无关代码 / 不弱化测试
#   3. set -euo pipefail + MAX_ITER + --max-budget-usd 三层硬上限防失控
#   4. claude -p 失败时 continue, 不让 set -e 终止整个 loop
#
# 用法:
#   bash scripts/auto-fix-tests.sh                    # 默认 10 轮, 单轮 $5
#   MAX_ITER=20 BUDGET=10 bash scripts/auto-fix-tests.sh
#
# 环境变量:
#   MAX_ITER     最大循环轮数 (默认 10)
#   BUDGET       单轮 agent 美元预算 (默认 5)
#   TEST_CMD     跑测试的命令 (默认: pytest -q)

set -euo pipefail

MAX_ITER="${MAX_ITER:-10}"
BUDGET="${BUDGET:-5}"
TEST_CMD="${TEST_CMD:-pytest -q}"

i=0
echo "auto-fix-tests: TEST_CMD='$TEST_CMD' MAX_ITER=$MAX_ITER BUDGET=\$$BUDGET"

while [ "$i" -lt "$MAX_ITER" ]; do
  i=$((i + 1))
  echo
  echo "=== iteration $i / $MAX_ITER ==="

  # 先 check — 已绿就别调 agent
  if eval "$TEST_CMD"; then
    echo "Green in $i iterations."
    exit 0
  fi

  # 再 fix — agent 失败时不让 set -e 终止整个 loop
  if ! claude -p "Tests are failing. Run: $TEST_CMD
Read the FIRST failure only. Make the smallest fix that resolves it.
Do not touch unrelated code. Do not weaken tests (no skip / mock / delete)." \
      --permission-mode acceptEdits \
      --max-budget-usd "$BUDGET"; then
    echo "claude agent failed at iteration $i, continuing"
  fi
done

echo
echo "Cap of $MAX_ITER reached, tests still red."
exit 1