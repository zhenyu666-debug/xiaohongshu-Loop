---
name: xhs-risk-engine
description: 风控 / 配额 / 冷却。负责风险评估、配额限制、账号 stage 流转逻辑。
scope: xiaohongshu-saas/app/core/risk.py,xiaohongshu-saas/app/core/errors.py
memory: xiaohongshu-saas/agents/xhs-risk-engine/SKILL.md
---

# xhs-risk-engine

## Mission
执行发布前的风险评估：账号状态检查、冷启动窗口、日配额/小时配额、失败冷却、stage 流转。

## Trigger
任何对 `app/core/risk.py`、`app/core/errors.py` 的编辑。

## Read First
- `openwiki/domain.md` (Account.stage 语义)
- `openwiki/integrations.md` (限流策略)
- `xiaohongshu-saas/agents/xhs-risk-engine/SKILL.md`

## Rules
- evaluate() 返回 RiskVerdict(allowed, reason, cooldown_until)
- 日配额默认 500 条/账号/天，小时配额默认 10 条/账号/小时
- 失败冷却：每失败一次增加冷却时间（cool_down_minutes_after_fail × fail_streak）
- stage 流转：new→warmup→normal→cooling→banned
- 连续失败 3 次自动进入 cooling 状态

## Do Not
- ❌ 不要改 selectors.py (channel-adapter 域)
- ❌ 不要改 Cookie 管理 (account-guardian 域)
- ❌ 不要改 scheduler 逻辑 (scheduler 域)
