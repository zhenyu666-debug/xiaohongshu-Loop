# xhs-release-engineer SKILL.md

## 当前状态
v0.6.2 MSI 已发布 (159 MB)。product.wxs 存在 CNDL1098/CNDL1077 candle 警告需修复。

## 关键文件索引
1. `installer/wix/product.wxs` - WiX MSI 配置
2. `installer/build.ps1` - 构建脚本 (版本管理)
3. `scripts/console_gui.py` - GUI launcher
4. `scripts/build_launcher.py` - PyInstaller 构建

## 最近改动
- 2026-07-09: 创建 SKILL.md，初始化永久记忆
- 2026-07-08: v0.6.2 MSI 发布 (fccd4b7)
- 2026-07-09: TODO: 修 CNDL1098/CNDL1077 candle 警告，打 v0.6.3 MSI

## Next 待办
- [P0] 修复 product.wxs CNDL1098/CNDL1077 警告
- [P0] 打 v0.6.3 MSI (installer/output/xhs-saas-console-0.6.3.msi)
- [P1] PyInstaller 6.x on Python 3.11 重建验证
- [P2] 优化 MSI 体积 (159 MB → < 120 MB)
