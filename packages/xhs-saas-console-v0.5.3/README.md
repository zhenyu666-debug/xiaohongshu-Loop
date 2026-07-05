# xhs-saas-console v0.5.3 (onefile) - 一体化控制台

> 一个 .exe,啥都不需要,双击就开。

---

## 这个包包含什么

| 文件 | 大小 | 说明 |
|---|---|---|
| xhs-saas-console.exe | 195.6 MB | 唯一一个文件!  内嵌 Python + Qt + WebView2 + 所有依赖 |
| install.bat | 3 KB | 一键安装 (可选) |
| uninstall.bat | 1 KB | 一键卸载 (可选) |
| manifest.json | 1 KB | 版本元数据 |
| README.md | 2 KB | 本文件 |

ONE-FILE 优点:
- 一个文件可以丢到任何地方 (U盘 / 邮件 / 桌面)
- 不需要安装 Python / Qt / 任何依赖
- 第一次启动 2-4s (解压到 %LOCALAPPDATA% 内置临时目录)
- 第二次启动 1-2s (已有缓存)

---

## 三种使用方式

### A. 一键安装 (推荐)

1. 解压 xhs-saas-console-v0.5.3.zip
2. 双击 install.bat
3. 桌面双击 xhs-saas-console 图标

### B. 绿色版 (不需要安装)

1. 解压到任何目录
2. 双击 xhs-saas-console.exe

完事。  整个世界只需要这一个 .exe。

### C. 拷到U盘 / 邮件附件

xhs-saas-console.exe 这一个文件就是全部。  195 MB。

---

## 启动后自动拉起的服务

| 服务 | 端口 | URL | 用途 |
|---|---|---|---|
| launcher status | 8765 | http://127.0.0.1:8765 | 状态查询 |
| launcher GUI | 8766 | http://127.0.0.1:8766 | 控制台 GUI |
| xhs-saas | 8080 | http://127.0.0.1:8080 | 小红书发布 |
| pbp-api | 8090 | http://127.0.0.1:8090 | 候选分子 API |
| lakehouse-api | 8091 | http://127.0.0.1:8091 | 数据湖 API |

---

## 系统要求

- OS: Windows 10/11 (64-bit)
- Runtime: WebView2 Runtime (Win 10/11 默认已装)
- RAM: 512 MB
- Disk: 250 MB (exe 195 MB + runtime 缓存 ~50 MB)

若 WebView2 缺失: 从 https://developer.microsoft.com/microsoft-edge/webview2/ 下载安装。

---

## 故障排查

| 问题 | 解决 |
|---|---|
| 双击 exe 闪退 | 确认 WebView2 已装;以管理员运行一次 |
| 端口被占用 | netstat -ano \| findstr :8765 找到 PID 后 taskkill /F /PID pid |
| 启动后白屏 | 等 3-5s (Qt WebEngine 首次初始化) |
| 想完全清理 | 运行 uninstall.bat; 或手动删 %LOCALAPPDATA%\xhs-saas-console\ |

---

## 许可

仅供内部使用。  不对外发布,不收集任何数据。
