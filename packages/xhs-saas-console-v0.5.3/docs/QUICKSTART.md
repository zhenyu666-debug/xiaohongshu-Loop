# 5 分钟上手

## 1. 启动

双击 xhs-saas-console.exe (或桌面的 xhs-saas-console 图标)。

首次启动:
- 解压到 %LOCALAPPDATA%\xhs-saas-console\runtime\ (~3s)
- WebView2 窗口弹出 (~2s)
- 4 服务自动启动 (~10s)
- 托盘图标出现

## 2. 检查状态

控制台 GUI:
- 4 块卡片显示 8765/8766/8080/8090/8091 的 UP/DOWN
- Start all / Stop all 按钮
- 实时日志滚动

命令行:
curl http://127.0.0.1:8765/status
curl http://127.0.0.1:8080/api/v1/health/all

## 3. 使用业务服务

- http://127.0.0.1:8080/docs
- http://127.0.0.1:8090/docs
- http://127.0.0.1:8091/docs

## 4. 关闭

右键托盘图标 -> Quit。
