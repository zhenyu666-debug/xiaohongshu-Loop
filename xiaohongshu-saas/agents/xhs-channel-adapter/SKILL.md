# xhs-channel-adapter SKILL.md

## 当前状态
小红书适配器已完成：Playwright 自动化、Cookie 管理、发布链路。selectors.py 需加 `input.upload-input` 兜底。

## 关键文件索引
1. `xiaohongshu-saas/app/channels/xiaohongshu/adapter.py` - XiaohongshuAdapter
2. `xiaohongshu-saas/app/channels/xiaohongshu/selectors.py` - DOM 选择器
3. `xiaohongshu-saas/app/channels/douyin/adapter.py` - DouyinAdapter (stub)
4. `xiaohongshu-saas/app/channels/base.py` - ChannelAdapter 抽象基类

## 最近改动
- 2026-07-09: 创建 SKILL.md，初始化永久记忆
- 2026-07-08: v0.6.2 修复 _maybe_rotate 逻辑 bug
- 2026-07-09: TODO: selectors.py 加 `input.upload-input` 兜底

## Next 待办
- [P0] selectors.py 加 `input.upload-input` 兜底
- [P1] 完善 DouyinAdapter (NotImplementedError → 真实实现)
- [P2] 添加 UI 改版自动检测机制
