# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Notes
- **fraud-risk-engine v0.3.0 / 子项目 fraud-risk-engine v0.3.0** — TigerLily edge-feature operators (hadamard/diff/l1/l2/concat/cosine), TIGER graph-robustness measures (stdlib-only subset — density, clustering, diameter, connectivity, assortativity, spectral radius), MedGraph Synthea integration (schema + 6 GSQL queries + loader + `/api/medgraph/*` endpoints + MedGraphView), and full GDSL v4.4.0_dev import (69 GSQL queries across Centrality / Classification / Community / GraphML / Path / Patterns / Similarity / TLP). Pytest 110/110 green. See [`fraud-risk-engine/CHANGELOG.md`](fraud-risk-engine/CHANGELOG.md) for full details.
  子项目 fraud-risk-engine v0.3.0：TigerLily 边特征算子（hadamard/diff/l1/l2/concat/cosine）、TIGER 图鲁棒性度量（仅 stdlib 子集——密度、聚类、直径、连通度、同配性、谱半径估计）、MedGraph Synthea 集成（schema + 6 条 GSQL 查询 + loader + `/api/medgraph/*` 端点 + MedGraphView）、完整 GDSL v4.4.0_dev 导入（69 条 GSQL 查询，覆盖 Centrality / Classification / Community / GraphML / Path / Patterns / Similarity / TLP）。pytest 110/110 通过。详见 [`fraud-risk-engine/CHANGELOG.md`](fraud-risk-engine/CHANGELOG.md)。

### Fixed
- `CHANGELOG.md` is now stored as UTF-8 (was UTF-16 LE with BOM up through `d629806`), so `git diff` shows proper text patches instead of "Binary files differ".
  `CHANGELOG.md` 现在以 UTF-8 存储（`d629806` 之前为 UTF-16 LE 带 BOM），`git diff` 将显示文本补丁而非「Binary files differ」。

### Notes
- Added `xhs-saas-console.exe` (onefile, 195 MB) as a sibling asset to the v0.6.1 release, alongside the 159 MB MSI; users who prefer direct-run have a smaller bootstrap.
  v0.6.1 release 新增 `xhs-saas-console.exe`（onefile，195 MB）作为补充下载，与 159 MB MSI 并列，供偏好直接运行的用户使用更小的引导文件。

## [0.6.4] - 2026-07-07
### Fixed
- XHS publish flow now routes through `/new/home` and clicks `发布图文笔记` before navigating to the publish form, matching the actual creator portal SPA flow.
  XHS 发布流改为先经过 `/new/home` 点击「发布图文笔记」再跳转到发布表单，对齐实际创作者中心的 SPA 行为。
- `scripts/rate_limit_probe.py` refactored: `OUT_DIR` resolved from repo root, correct middle-dot task name, async `load_account_and_task`, and `_Acct` stand-in for adapter.publish calls.
  `scripts/rate_limit_probe.py` 重构：`OUT_DIR` 从仓库根解析、修正任务名中的中点、async `load_account_and_task`、`_Acct` 替身适配器调用。

### Notes
- DOM inspector (`xiaohongshu-saas/scripts/_inspect_publish_dom.py`) confirms the publish page only exposes one editable element after click (`<input type="file" class="upload-input">`); the publish adapter still needs to be updated to wait on `input.upload-input` instead of the previous combined selector.
  DOM 探针（`xiaohongshu-saas/scripts/_inspect_publish_dom.py`）确认发布页点击后只暴露一个可编辑元素（`<input type="file" class="upload-input">`）；发布适配器仍需改为等待 `input.upload-input` 而非之前的组合选择器。

## [0.6.3] - 2026-07-06
### Fixed
- Console supervisor loop NameError: `cfg_enabled(svc)` -> `svc.get("enabled", True)` so `_supervise` (line 585) and the card-state read stay in sync.
  控制台监督循环 NameError：将 `cfg_enabled(svc)` 改为 `svc.get("enabled", True)`，让 `_supervise`（第 585 行）与卡片状态读取保持一致。

## [0.6.2] - 2026-07-06
### Fixed
- Fresh installs no longer crash on first import: added missing `email-validator==2.3.0` runtime dep; fixed `NameError: Tenant` in `_seed_default_tenant`; removed broken `User.tenant` many-to-many declared with `secondary=`.
  新装环境不再首次 import 崩溃：补齐缺失的运行时依赖 `email-validator==2.3.0`；修复 `_seed_default_tenant` 里的 `NameError: Tenant`；移除错误的 `User.tenant` 多对多（带 `secondary=`）。
- pbp-api and lakehouse-api are both enabled and serving data; previously the console showed their cards as gray "未启用" placeholders because the source files were missing from the working tree.
  pbp-api 与 lakehouse-api 均已启用并提供数据；之前控制台显示为灰色「未启用」占位符，原因是工作树缺失源码。
- Console `main()` now auto-calls `start_all()` so the WebView opens with services already starting, not waiting on a button click.
  控制台 `main()` 现在自动调用 `start_all()`，WebView 打开时服务已在启动，无需再点按钮。

## [0.6.1] - 2026-07-06
### Changed
- Repo split: donor-screener-*, get-jobs (recruit crawlers), li_s_additives, vnpy, uml-p-screener moved to private repos. Main repo focuses on xiaohongshu-saas.
- Slimmed home README to focus on xiaohongshu-Loop core.
- **MSI install location is now user-selectable / MSI 安装位置支持用户自定义** — switched `WixUI_Minimal` -> `WixUI_InstallDir`, bound `WIXUI_INSTALLDIR=INSTALLDIR`, and made `ARPINSTALLLOCATION` reflect the actual chosen folder.
  **MSI 安装位置支持用户自定义** —— 把 UI 从 `WixUI_Minimal` 换成 `WixUI_InstallDir`，绑定 `WIXUI_INSTALLDIR=INSTALLDIR`，并让 `ARPINSTALLLOCATION` 反映实际选择的目录。
- **MSI size down from 343 MB to 159 MB / MSI 体积从 343 MB 降至 159 MB** — switched `dist/xhs-saas-console.exe` payload from onefile (with embedded `_internal/`) to onedir, so the MSI no longer ships the entire launcher payload twice.
  MSI 体积从 343 MB 降到 159 MB——把 `dist/xhs-saas-console.exe` 的 payload 从 onefile（自带 `_internal/`）切换到 onedir，MSI 不再把启动器 payload 重复打包两次。
- **Multi-tenant auth API / 多租户鉴权 API** — accounts / tasks / misc endpoints now scope queries by `principal.tenant.id` and stamp `tenant_id` on create. New `auth`, `billing`, `tenants` routers + `app.core.auth` / `app.core.security` helpers.
  accounts / tasks / misc 接口现在按 `principal.tenant.id` 隔离查询，并在创建时写入 `tenant_id`。新增 `auth`、`billing`、`tenants` 三个 router 与 `app.core.auth` / `app.core.security` 工具模块。

### Added
- CHANGELOG.md, FAQ.md, CONTRIBUTING.md, CODE_OF_CONDUCT.md
- .github/ISSUE_TEMPLATE/{bug_report,feature_request}.yml
- .github/PULL_REQUEST_TEMPLATE.md
- .github/release.yml — controls how "Generate release notes" organises PRs into sections
- GitHub Topics + Discussions enabled
- **Branded .ico for desktop & start-menu shortcuts / 桌面与开始菜单快捷方式使用品牌 logo** — multi-size `assets/ico/xhs-saas-console.ico` (256, 128, 64, 48, 32, 24, 16) is generated by `scripts/build_icon.py`, embedded into the exe by PyInstaller (`--icon`), and bound to all `.lnk` shortcuts via `<Icon Id="AppIcon">` in WiX.
  **桌面与开始菜单快捷方式使用品牌 logo 图标** —— 多分辨率 `assets/ico/xhs-saas-console.ico` (256, 128, 64, 48, 32, 24, 16) 通过 `scripts/build_icon.py` 生成，PyInstaller 通过 `--icon` 嵌入到 exe 资源，并通过 WiX 中 `<Icon Id="AppIcon">` 绑定到所有 `.lnk` 快捷方式。
- `scripts/build_icon.py` — single-entry PNG -> multi-size ICO generator.
- `scripts/_build_icon_once.py` — one-shot helper invoked from build pipelines.
- `installer/build.ps1 -Publish` — one-shot MSI build + `gh release create` pipeline.
  `installer/build.ps1 -Publish` —— 一键构建 MSI + `gh release create` 的发布流水线。
- `installer/docs/RELEASE_NOTES/v0.6.1.md` — bilingual release notes published verbatim into the GitHub Release body.
  `installer/docs/RELEASE_NOTES/v0.6.1.md` —— 中英双语 release notes，直接粘贴到 GitHub Release 描述。

## [0.6.0] - 2026-07-05

### Added  新增
- **MSI installer / MSI 安装程序** (PerUser scope). Drops into Add/Remove Programs, Start Menu + Desktop shortcut; no admin elevation.
  以每用户（PerUser）范围打包的 MSI 安装程序——放入「添加/删除程序」，自动建立「开始菜单」与「桌面」快捷方式，无需管理员权限提升。
- **One-click GUI launcher / 一键式图形界面启动器** — double-click on the shortcut boots `xhs-saas-console.exe` (~195 MB) which auto-starts the three services.
  双击快捷方式即可启动 `xhs-saas-console.exe`（约 195 MB），自动拉起三项服务：
  - `xhs-saas` on :8080
  - `pbp-api` on :8090
  - `lakehouse-api` on :8091
- **Dual delivery / 两种交付格式** — same source, two artifacts: `xhs-saas-console-0.6.0.exe` for direct-run users, `xhs-saas-console-0.6.0.msi` for managed deployment.
  同一源码，两种交付格式：`xhs-saas-console-0.6.0.exe` 面向「直接运行」用户；`xhs-saas-console-0.6.0.msi` 用于托管部署。
- **Silent install + clean uninstall / 静默安装 + 干净卸载** — `msiexec /i ... /qn` + `msiexec /x {CB49ED5C-30E2-4F98-99DC-63A15816DC5E}`.
  支持静默安装与干净卸载：`msiexec /i ... /qn` 与 `msiexec /x {CB49ED5C-30E2-4F98-99DC-63A15816DC5E}`。
- **Auto-upgrade from v0.5.x / 从 v0.5.x 自动升级** — Installer uses UpgradeCode to detect prior versions and upgrades in place (no uninstall step).
  安装程序通过 UpgradeCode 自动检测先前版本，可在不卸载的情况下原地升级。
- **Release notes scaffolding / 发布说明脚手架** — `.github/release.yml` + `installer/docs/RELEASE_NOTES/` (bilingual EN/CN templates).
  发布说明基础设施：`.github/release.yml` 控制 PR 标签自动分类，外加 `installer/docs/RELEASE_NOTES/` 目录（提供中英双语模板）。

### Known issues  已知问题
- MSI bundles full `dist/` + `_internal/`, totaling ~343 MB. Users who want a smaller download should pick the `.exe` release.
  MSI 包含完整的 `dist/` + `_internal/`，总体积约 343 MB；想要更小下载包的用户请改用 `.exe` 版本。

## [0.5.3] - 2026-07-05

### Added
- Unified Console desktop GUI: single-file .exe (195 MB, PyInstaller --onefile). Boots xiaohongshu-saas + pbp-api + lakehouse-api together.
  - Status: http://127.0.0.1:8765
  - WebView2 GUI: http://127.0.0.1:8766
  - Tray icon + Start/Stop/Open/Quit buttons + rolling log tail
- packages/xhs-saas-console-v0.5.3.zip release bundle (install.bat / uninstall.bat / README.md / docs/)
- dist/xhs-saas-console.exe single-file launcher
- Git LFS tracking *.exe and *.zip

### Changed
- scripts/build_launcher.py: --onedir -> --onefile + --runtime-tmpdir %LOCALAPPDATA%\xhs-saas-console\runtime
- .gitignore: added node_modules/, dist/*/_internal/, debug scripts

## [0.5.2] - 2026-07-04

### Added
- pbp-api (port 8090): candidates API (donor-screener-pbp integration)
- lakehouse-api (port 8091): data lake API (Trino wrapper + seed fallback)

## [0.5.1] - 2026-06-28

### Added
- xhs-saas main service (port 8080): accounts / content factory / scheduler / risk / channels
- Playwright browser pool
- Redis + Postgres orchestration (docker compose up)

## [0.4.0] - 2026-06-10

### Added
- CI (xhs-saas-ci.yml): lint + pytest
- Auto-fix loop (auto-fix.yml): 5-layer defense (path filter + diff <= 1000 + secondary CI + concurrency + infinite-loop guard)

## [0.3.0] - 2026-05-22

### Added
- React/Vite console skeleton (xiaohongshu-saas/web/console)

## [0.2.0] - 2026-04-30

### Added
- xiaohongshu adapter (Playwright, image/video/topic/@mention/location)
- Content factory: templates + OpenAI rewrite

## [0.1.0] - 2026-03-15

### Added
- Initial project skeleton
- xiaohongshu-saas/ directory structure
- FastAPI template-only console

[Unreleased]: https://github.com/zhenyu666-debug/xiaohongshu-Loop/compare/v0.6.4...HEAD
[0.6.4]: https://github.com/zhenyu666-debug/xiaohongshu-Loop/compare/v0.6.3...v0.6.4
[0.6.3]: https://github.com/zhenyu666-debug/xiaohongshu-Loop/compare/v0.6.2...v0.6.3
[0.6.2]: https://github.com/zhenyu666-debug/xiaohongshu-Loop/compare/v0.6.1...v0.6.2
[0.6.1]: https://github.com/zhenyu666-debug/xiaohongshu-Loop/compare/v0.6.0...v0.6.1
[0.6.0]: https://github.com/zhenyu666-debug/xiaohongshu-Loop/compare/v0.5.3...v0.6.0
[0.5.3]: https://github.com/zhenyu666-debug/xiaohongshu-Loop/compare/v0.5.2...v0.5.3
[0.5.2]: https://github.com/zhenyu666-debug/xiaohongshu-Loop/compare/v0.5.1...v0.5.2
[0.5.1]: https://github.com/zhenyu666-debug/xiaohongshu-Loop/compare/v0.4.0...v0.5.1
[0.4.0]: https://github.com/zhenyu666-debug/xiaohongshu-Loop/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/zhenyu666-debug/xiaohongshu-Loop/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/zhenyu666-debug/xiaohongshu-Loop/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/zhenyu666-debug/xiaohongshu-Loop/releases/tag/v0.1.0