---
name: xhs-channel-adapter
description: 适配器 / 选择器 / 发布链路。负责 XiaohongshuAdapter 的 Playwright 自动化、DouyinAdapter 接入、DOM 选择器维护。
scope: xiaohongshu-saas/app/channels/**
memory: xiaohongshu-saas/agents/xhs-channel-adapter/SKILL.md
---

# xhs-channel-adapter

## Mission
让 XiaohongshuAdapter 在 UI 改版后仍能跑通发布/扫码/heartbeat；在 selectors.py 单文件集中改选择器。

## Trigger
任何对 `app/channels/**` 的编辑。

## Read First
- `openwiki/integrations.md` (Cookie + proxy + UI 改版应急)
- `xiaohongshu-saas/agents/xhs-channel-adapter/SKILL.md`

## Rules
- selectors.py 是唯一允许改选择器的地方
- 任何 AccountError 不允许 raise，要回 PublishResult(success=False,...)
- publish 链路兜底必须捕获所有异常，error 字段保留类型名
- _navigate_to_publish_form 加 180s 总超时
- FILE_INPUT 默认 `input[type=file][accept^='"'"'image'"'"']`，需加 `input.upload-input` 兜底

## Do Not
- ❌ 不要改 Account 模型字段名 (account-guardian 域)
- ❌ 不要改风险引擎参数 (risk-engine 域)
