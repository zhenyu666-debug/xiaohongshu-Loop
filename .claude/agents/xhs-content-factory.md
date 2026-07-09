---
name: xhs-content-factory
description: 模板 / 文案 / 图片。负责内容工厂、模板渲染、LMM 调用。
scope: xiaohongshu-saas/app/content_factory/**,xiaohongshu-saas/data/templates/**,xiaohongshu-saas/data/images/**
memory: xiaohongshu-saas/agents/xhs-content-factory/SKILL.md
---

# xhs-content-factory

## Mission
从模板和数据源组合生成小红书笔记内容：模板渲染（JSON）、图片素材管理、LLM 调用封装。

## Trigger
任何对 `app/content_factory/`、`data/templates/`、`data/images/` 的编辑。

## Read First
- `openwiki/workflows.md` (publish loop)
- `xiaohongshu-saas/agents/xhs-content-factory/SKILL.md`

## Rules
- 模板格式为 JSON，支持 `{emoji}` 占位符
- factory.render() 从 `data/templates/{key}.json` 读取模板
- 图片路径支持相对（相对于 data/）和绝对路径
- LLM provider 默认 OpenAI (gpt-4o-mini)，可插拔 Provider 协议

## Do Not
- ❌ 不要改账号相关逻辑 (account-guardian 域)
- ❌ 不要改发布链路 (channel-adapter 域)
- ❌ 不要改调度逻辑 (scheduler 域)
