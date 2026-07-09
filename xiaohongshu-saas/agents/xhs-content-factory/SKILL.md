# xhs-content-factory SKILL.md

## 当前状态
内容工厂已完成：factory.render() 从 `data/templates/{key}.json` 读取模板，支持 `{emoji}` 占位符。PIL 生成占位图。

## 关键文件索引
1. `xiaohongshu-saas/app/content_factory/__init__.py` - 内容工厂入口
2. `xiaohongshu-saas/app/content_factory/factory.py` - 模板渲染逻辑
3. `xiaohongshu-saas/data/templates/demo.json` - demo 穿搭模板
4. `xiaohongshu-saas/data/images/demo_1.jpg` - 占位图片

## 最近改动
- 2026-07-09: 创建 SKILL.md，初始化永久记忆
- 2026-07-08: v0.6.2 创建 demo 模板 + PIL 占位图

## Next 待办
- [ ] 支持更多模板类型（美妆/旅行/美食）
- [ ] 添加模板预览功能
- [ ] 集成真实图片生成（暂用 PIL 占位）
