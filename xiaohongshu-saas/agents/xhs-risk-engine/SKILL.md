# xhs-risk-engine SKILL.md

## 当前状态
风控引擎已完成：日配额(500)/小时配额(10)、失败冷却、stage 流转。v0.6.2 已稳定运行。

## 关键文件索引
1. `xiaohongshu-saas/app/core/risk.py` - evaluate(), mark_success(), mark_failure()
2. `xiaohongshu-saas/app/core/errors.py` - AccountError, PublishError
3. `xiaohongshu-saas/app/core/config.py` - risk 参数配置

## 最近改动
- 2026-07-09: 创建 SKILL.md，初始化永久记忆
- 2026-07-08: v0.6.2 完善风控逻辑

## Next 待办
- [ ] 动态配额调整（基于账号历史表现）
- [ ] 支持自定义风控规则
- [ ] 添加风控事件告警通知
