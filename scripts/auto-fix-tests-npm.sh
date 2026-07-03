#!/usr/bin/env bash
# auto-fix-tests-npm.sh — 自动让 agent 修失败的 npm 测试
#
# 思路: CI 红了 → 让 Claude agent 自动读失败 → 做最小修复 → 再跑 → 直到绿 / 烧光预算
#
# 这是 auto-fix-tests.sh 的 npm 专属版本, 默认 TEST_CMD="npm test --silent"。
# Python / pytest 用 auto-fix-tests.sh。
#
# 设计要点:
#   1. "check first, fix second" — 已绿就别调 agent, 避免浪费一轮预算
#   2. agent prompt 三条约束: 最小改动 / 不碰无关代码 / 不弱化测试
#   3. set -euo pipefail + MAX_ITER + --max-budget-usd 三层硬上限防失控
#   4. claude -p 失败时 continue, 不让 set -e 终止整个 loop
#
# ⚠️ npm 测试常自带 watch 模式 (jest --watchAll, vitest --watch, cypress run --watch),
#    会让外层 loop 永远卡住。脚本默认强制 export CI=1, 让 jest/vitest/cypress/playwright
#    拒绝 watch 模式一次性跑完。CI=1 已是 npm 生态约定, 不影响用户透传的 TEST_CMD。
#
# 用法:
#   bash scripts/auto-fix-tests-npm.sh               # 默认 10 轮, 单轮 $5
#   MAX_ITER=20 BUDGET=10 bash scripts/auto-fix-tests-npm.sh
#
# 环境变量:
#   MAX_ITER     最大循环轮数 (默认 10)
#   BUDGET       单轮 agent 美元预算 (默认 5)
#   TEST_CMD     跑测试的命令 (默认: npm test --silent -- --watchAll=false)
#                - 默认透传 -- --watchAll=false 给 jest, 强制非交互
#                - vitest 用户: TEST_CMD="vitest run"
#                - cypress 用户: TEST_CMD="cypress run"
#                - pnpm 用户: TEST_CMD="pnpm test --silent -- --watchAll=false"
#                自定义 TEST_CMD 时无需再加 CI=1 前缀 (脚本已 export)。

set -euo pipefail

MAX_ITER="${MAX_ITER:-10}"
BUDGET="${BUDGET:-5}"
TEST_CMD="${TEST_CMD:-npm test --silent -- --watchAll=false}"

# 强制 CI=1 — jest/vitest/cypress/playwright 都认这个环境变量拒绝 watch 模式。
# 用户自定义 TEST_CMD 时也会被这个 CI=1 包装, 不需要再手动加。
export CI=1

i=0
echo "auto-fix-tests-npm: TEST_CMD='$TEST_CMD' MAX_ITER=$MAX_ITER BUDGET=\$$BUDGET"

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
Do not touch unrelated code. Do not weaken tests (no skip / .skip() / xit / delete)." \
      --permission-mode acceptEdits \
      --max-budget-usd "$BUDGET"; then
    echo "claude agent failed at iteration $i, continuing"
  fi
done

echo
echo "Cap of $MAX_ITER reached, tests still red."
exit 1