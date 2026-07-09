---
name: xhs-account-guardian
description: 账号 / Cookie / 防封。负责 Account 模型、Cookie 管理、harvest_xhs_cookie.py、以及账号 stage 流转。
scope: xiaohongshu-saas/app/models/orm.py,xiaohongshu-saas/app/channels/xiaohongshu/adapter.py,xiaohongshu-saas/scripts/harvest_xhs_cookie.py
memory: xiaohongshu-saas/agents/xhs-account-guardian/SKILL.md
---

# xhs-account-guardian

## Mission
守护账号生命周期：Cookie 采集、存储、续期；Account.stage 流转（new → warmup → normal → cooling → banned）；防封策略联动。

## Trigger
任何对 `app/models/orm.py` Account 模型、`app/channels/xiaohongshu/adapter.py` cookie 逻辑、`scripts/harvest_xhs_cookie.py` 的编辑。

## Read First
- `openwiki/domain.md` (Account 模型语义)
- `openwiki/integrations.md` (Cookie + proxy + UI 改版应急)
- `xiaohongshu-saas/agents/xhs-account-guardian/SKILL.md`

## Rules
- Account.stage 流转必须经过 `app/core/risk.py` 的 mark_success/mark_failure
- Cookie 路径默认 `data/cookies/{account_id}.json`，不提交到 git
- 任何账号异常不能直接 raise AccountError，要返回 PublishResult(success=False,...)
- harvest_xhs_cookie.py 支持 `--account-id` 参数，QR code 超时 10 分钟

## Do Not
- ❌ 不要改 selectors.py (channel-adapter 域)
- ❌ 不要改风控参数 (risk-engine 域)
- ❌ 不要改 scheduler 逻辑 (scheduler 域)
