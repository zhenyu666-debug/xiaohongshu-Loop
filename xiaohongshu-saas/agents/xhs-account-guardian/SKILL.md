# xhs-account-guardian SKILL.md

## 当前状态
账号生命周期管理已完成：Account.stage 流转、Cookie 采集/存储/续期。v0.6.2 已发布。

## 关键文件索引
1. `xiaohongshu-saas/app/models/orm.py` - Account 模型 (tenant_id, stage, cookie_path)
2. `xiaohongshu-saas/app/channels/xiaohongshu/adapter.py` - XiaohongshuAdapter (cookie 逻辑)
3. `xiaohongshu-saas/scripts/harvest_xhs_cookie.py` - QR code 登录脚本
4. `xiaohongshu-saas/app/core/risk.py` - stage 流转 mark_success/mark_failure
5. `xiaohongshu-saas/data/cookies/` - Cookie JSON 存储目录 (git-ignored)

## 最近改动
- 2026-07-09: 创建 SKILL.md，初始化永久记忆
- 2026-07-08: v0.6.2 发布，账号系统稳定

## Next 待办
- [ ] 增强 Cookie 续期逻辑（检测过期自动提醒）
- [ ] 支持多账号批量扫码
- [ ] 添加账号健康度评分机制
