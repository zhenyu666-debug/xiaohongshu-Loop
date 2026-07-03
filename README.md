<!-- ============================================================ -->
<!-- xiaohongshu-Loop · 仓库首页                                  -->
<!-- 替换为真实品牌 LOGO 后，请同步更新顶部 hero 图和 favicon      -->
<!-- ============================================================ -->

<p align="center">
  <img src="https://img.shields.io/badge/xiaohongshu--Loop-FF2442?style=for-the-badge&logo=data:image/svg%2bxml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAyNCAyNCI+PHBhdGggZD0iTTEyIDJsMyA3aDdsLTUuNSA0LjUgMiA4LTYuNS00LjUtNi41IDQuNSAyLTgtNS41LTQuNWg3eiIgZmlsbD0iI2ZmZiIvPjwvc3ZnPg==&logoColor=white&labelColor=FF2442" alt="xiaohongshu-Loop"/>
</p>

<h1 align="center">
  <sub>小红书起步 · 多渠道社媒 SaaS 中台</sub><br/>
  xiaohongshu-Loop
</h1>

<p align="center">
  <em>账号池 · 内容工厂 · 调度器 · 风控 · 渠道适配器 —— 五层解耦，一次接入，多渠道复用。</em>
</p>

<p align="center">
  <!-- 动态徽章（shields.io 实时拉取） -->
  <a href="https://github.com/zhenyu666-debug/xiaohongshu-Loop/stargazers"><img src="https://img.shields.io/github/stars/zhenyu666-debug/xiaohongshu-Loop?style=for-the-badge&logo=github&color=FF2442" alt="GitHub stars"/></a>
  <a href="https://github.com/zhenyu666-debug/xiaohongshu-Loop/network/members"><img src="https://img.shields.io/github/forks/zhenyu666-debug/xiaohongshu-Loop?style=for-the-badge&logo=github&color=FF6B81&logoColor=white" alt="GitHub forks"/></a>
  <a href="https://github.com/zhenyu666-debug/xiaohongshu-Loop/issues"><img src="https://img.shields.io/github/issues/zhenyu666-debug/xiaohongshu-Loop?style=for-the-badge&logo=github&color=1a1a1a" alt="GitHub issues"/></a>
  <a href="https://github.com/zhenyu666-debug/xiaohongshu-Loop/actions"><img src="https://img.shields.io/github/actions/workflow/status/zhenyu666-debug/xiaohongshu-Loop/xhs-saas-ci.yml?style=for-the-badge&logo=githubactions&logoColor=white&label=CI" alt="CI status"/></a>
  <a href="https://github.com/zhenyu666-debug/xiaohongshu-Loop/blob/main/LICENSE"><img src="https://img.shields.io/github/license/zhenyu666-debug/xiaohongshu-Loop?style=for-the-badge&color=blue" alt="License"/></a>
  <a href="https://www.python.org/"><img src="https://img.shields.io/badge/python-3.11%2B-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.11+"/></a>
</p>

<p align="center">
  <a href="#-快速开始">快速开始</a> · <a href="#-架构">架构</a> · <a href="#-demo">Demo</a> · <a href="xiaohongshu-saas/README.md">子项目文档</a>
</p>

---

> [!IMPORTANT]
> **首发渠道：小红书** · 架构预留抖音 / 快手 / 视频号 / B 站 / 知乎扩展位 · **中台骨架优先**，业务侧只关心"什么账号发什么内容什么时间发"。

## 核心能力矩阵

| 模块 | 能力 | 状态 |
|---|---|---|
| **账号池** | 多账号分组 · 阶段化（新号 / 冷启 / 正常 / 限流） · cookie 持久化与轮换 | 已上线 |
| **内容工厂** | 模板生成 · 占位符替换 (`{emoji}` / `{hour}`) · 可选 OpenAI 改写 | 已上线 |
| **调度器** | APScheduler 周期任务 · 间隔 + 抖动 · 时间窗口 · 失败冷却 | 已上线 |
| **风控** | 日 / 小时配额 · 人类化随机延迟 · 暖机期 · 代理轮换 | 已上线 |
| **渠道适配器** | 小红书（Playwright，图文 / 视频 / 话题 / @ / 位置） | 已上线 |
| **渠道适配器** | 抖音 / 快手 / 视频号 / B 站 / 知乎 | 占位（stub） |
| **控制台** | FastAPI 模板版 + React/Vite 完整版（`/console`） | 双版本 |
| **观测** | 结构化日志 · `/metrics` Prometheus · `/api/dashboard/summary` | 已上线 |
| **部署** | `docker compose up` 一键拉起 Web + Worker + Redis + Postgres | 已上线 |

## 架构

```mermaid
flowchart TB
  subgraph frontend[前端]
    Web[Web 控制台<br/>FastAPI 模板 / React]
  end

  subgraph core[中台核心 API]
    Accounts[账号池]
    Factory[内容工厂]
    Scheduler[调度器]
    Risk[风控]
    Audit[审计]
  end

  subgraph channels[渠道适配器]
    XhsAdapter[小红书<br/>Playwright]
    DyAdapter[抖音<br/>stub]
    OtherAdapter[其他渠道<br/>stub]
  end

  subgraph infra[基础设施]
    Pool[Playwright 浏览器池]
    Proxy[代理池]
    AI[OpenAI 改写]
    DB[(SQLite / Postgres)]
    MQ[(Redis)]
  end

  Web -->|REST + WS| core
  Scheduler -->|Celery / Redis| MQ
  MQ --> XhsAdapter
  MQ --> DyAdapter
  XhsAdapter --> Pool
  XhsAdapter --> Proxy
  Factory --> AI
  core --> DB
```

## Demo

> [!TIP]
> **真实截图 / GIF 替换占位**：把下面的占位图替换为 `docs/demo-loop.gif` / `docs/console.png`，GitHub 会自动渲染。

<!-- 替换占位：推荐尺寸 1280x720，文件 < 10 MB -->
<p align="center">
  <img src="https://via.placeholder.com/960x540/FF2442/ffffff?text=Loop+Demo+GIF+%E5%B7%B2%E5%B0%81%E5%AD%98%E5%88%B0+docs%2Fdemo-loop.gif" alt="Loop demo placeholder" width="960"/>
  <br/><sub><em>↑ 把 `docs/demo-loop.gif` 拖到仓库根，替换此占位图</em></sub>
</p>

<p align="center">
  <img src="https://via.placeholder.com/480x270/1a1a1a/ffffff?text=Console" alt="Console placeholder" width="480"/>
  <img src="https://via.placeholder.com/480x270/FF6B81/ffffff?text=Dashboard" alt="Dashboard placeholder" width="480"/>
</p>

## 快速开始

> [!NOTE]
> 详细文档见 [`xiaohongshu-saas/README.md`](xiaohongshu-saas/README.md)。下面给出 3 种主流启动方式。

### 方式 A：Docker 一键起（推荐）

```bash
git clone https://github.com/zhenyu666-debug/xiaohongshu-Loop.git
cd xiaohongshu-Loop/xiaohongshu-saas/deploy
docker compose up -d
# Web:        http://localhost:8080
# Prometheus: http://localhost:9090
```

### 方式 B：本地开发

```bash
cd xiaohongshu-saas
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev,ai]"
playwright install chromium

cp .env.example .env       # 填 OPENAI_API_KEY（可选）
python -m scripts.init_db
uvicorn app.main:app --reload --port 8080
```

### 方式 C：React 控制台（完整后台）

```bash
cd xiaohongshu-saas/web/console
npm install
npm run dev     # 开发模式 http://localhost:5173/console/
npm run build   # 打包到 dist/
```

Vite 已配置代理，开发时 `/api` 请求自动转发到 `http://localhost:8080`。

## 渠道适配器扩展

每个渠道只需实现 [基础协议](xiaohongshu-saas/app/channels/base.py)：

```python
class ChannelAdapter(Protocol):
    name: str
    async def login(self, account: Account) -> None: ...
    async def publish(self, account: Account, content: ContentItem) -> PublishResult: ...
    async def heartbeat(self, account: Account) -> AccountHealth: ...
```

注册到中台即可：

```python
# xiaohongshu-saas/app/channels/registry.py
register(XiaohongshuAdapter())
# register(DouyinAdapter())
# register(KuaishouAdapter())
```

## 风控默认策略

| 策略 | 默认值 | 配置项 |
|---|---|---|
| 单账号日发帖上限 | 5 | `DAILY_POST_LIMIT_PER_ACCOUNT` |
| 单账号小时发帖上限 | 2 | `HOURLY_POST_LIMIT_PER_ACCOUNT` |
| 失败冷却 | 30 分钟 | `COOL_DOWN_MINUTES_AFTER_FAIL` |
| 人类化随机延迟 | 1.2 – 4.5 秒 | `HUMAN_DELAY_MIN_MS` / `_MAX_MS` |
| 代理轮换间隔 | 每 20 条 | `PROXY_ROTATE_EVERY` |
| 新号独立发帖前暖机时长 | 24 小时 | `WARMUP_HOURS_BEFORE_SOLOPOST` |

> [!WARNING]
> 强烈建议：账号数量 × 单号日上限 < 平台安全阈值 + 30% 冗余。

## Roadmap

- [x] 中台骨架（账号 / 内容 / 任务 / 风控）
- [x] 小红书适配器（Playwright + cookie 复用）
- [x] 内容工厂（模板 + OpenAI 改写）
- [x] Docker 一键起
- [x] 仓库根 README 装修（Hero + Badge + 架构图）
- [ ] 抖音 / 视频号适配器
- [ ] 多租户（团队 / 角色 / 计费）
- [ ] 移动端 H5 控制台
- [ ] 数据回流（曝光 / 互动 → 选题反哺）
- [ ] 真实 demo GIF + 控制台截图替换占位

## Contributing

PR / Issue 欢迎：

- [贡献指南（占位）](CONTRIBUTING.md)
- [Issue 模板（占位）](.github/ISSUE_TEMPLATE.md)
- [行为准则（占位）](CODE_OF_CONDUCT.md)

本地开发流程：

```bash
cd xiaohongshu-saas
ruff check .
pytest -q tests
```

## Disclaimer

> 本项目仅用于**工程研究与自有账号自动化**，请：
> 1. 严格遵守各平台协议与机器人规范；
> 2. 不得用于刷量、灰产、虚假宣传等违规场景；
> 3. 因使用不当造成的封号、法律风险由使用者自行承担。

## License

[MIT](LICENSE) · 详见 [`LICENSE`](LICENSE) 文件。

---

<p align="center">
  <sub>
    <a href="https://github.com/zhenyu666-debug/xiaohongshu-Loop/blob/main/xiaohongshu-saas/README.md">完整文档</a>
    · <a href="https://github.com/zhenyu666-debug/xiaohongshu-Loop/issues">反馈 Bug</a>
    · <a href="https://github.com/zhenyu666-debug/xiaohongshu-Loop/issues">提需求</a>
  </sub>
</p>

<!-- Star History: 替换 owner/repo 后自动生成 -->
<p align="center">
  <img src="https://img.shields.io/github/stars/zhenyu666-debug/xiaohongshu-Loop?style=social" alt="Star this repo"/>
</p>