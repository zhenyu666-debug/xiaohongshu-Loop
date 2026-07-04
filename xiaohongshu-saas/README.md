# xiaohongshu-Loop · 小红书起步的多渠道 SaaS 中台 · 自动发帖机器人

> 一个面向**多账号 / 多渠道**社媒运营的 SaaS 中台，**首发渠道：小红书**。后续可平滑扩展到抖音、快手、视频号、B 站、知乎等。
> 核心思路：把"账号池 · 内容工厂 · 调度器 · 渠道适配器 · 风控"解耦，做一个可观测、可灰度的中台骨架。

---

## 📌 概述

| 项 | 说明 |
| --- | --- |
| 项目名 | `xiaohongshu-Loop`（仓库根名）/ `xhs-saas`（应用名） |
| 首发渠道 | 小红书（图文 / 视频笔记 + 话题 + @ + 位置 + 定时 + 循环） |
| 后续渠道 | 抖音、快手、视频号、B 站、知乎（按 `ChannelAdapter` 协议实现） |
| 核心形态 | 多账号 · 多渠道 · 任务调度 · 风控 · 内容工厂 五层中台 |
| 主要技术栈 | FastAPI · Playwright · Celery · Redis · Postgres · React/Vite · Prometheus · loguru |
| 部署形态 | 本地 Docker / 阿里云 ECS / 自有 K8s |
| License | 见文末 "License" 节（**待你确认**，默认占位未声明） |

---

## ✨ 亮点

- **中台架构**：账号 / 内容 / 任务 / 风控 / 渠道五层解耦，业务侧只关心"什么账号发什么内容什么时间发"。
- **小红书首发**：内置 Playwright 适配器，支持图文 / 视频笔记、话题、@、位置，定时与循环。
- **内容工厂**：内置模板生成 + 可选 OpenAI 改写，支持多账号人设差异化。
- **风控优先**：账号分级（新号→冷启→正常）、日 / 小时配额、失败冷却、人类化随机延迟、代理轮换。
- **可观测**：结构化日志（loguru）、任务状态机、Prometheus 指标、健康检查。
- **易部署**：`docker compose up -d` 一键拉起 Web + Worker + Redis + Postgres。

---

## 🧱 架构

```
                ┌───────────────────────────────────────┐
                │           Web 控制台 (FastAPI)         │
                │   账号 / 内容 / 任务 / 数据看板        │
                └─────────────────┬─────────────────────┘
                                  │  REST + WS
                ┌─────────────────▼─────────────────────┐
                │              中台核心 (API)            │
                │  账号池 · 内容工厂 · 调度 · 风控 · 审计  │
                └─────────────────┬─────────────────────┘
                                  │ Celery / Redis
        ┌─────────────┬───────────▼───────────┬─────────────┐
        │             │                       │             │
   ┌────▼────┐   ┌────▼────┐             ┌────▼────┐   ┌────▼────┐
   │小红书适配│   │抖音适配 │  ...        │ AI 改写  │   │ 代理池  │
   │Playwright│   │(后续)   │             │ OpenAI   │   │         │
   └────┬─────┘   └─────────┘             └─────────┘   └─────────┘
        │
   ┌────▼──────────────────────────────┐
   │  Playwright 浏览器池 (有头 / 无头)  │
   └───────────────────────────────────┘
```

---

## 📁 目录结构

```
xiaohongshu-saas/
├─ app/
│  ├─ main.py                  # FastAPI 入口
│  ├─ core/                    # 配置、日志、安全、依赖注入
│  ├─ api/                     # 路由：accounts / contents / tasks / dashboard
│  ├─ models/                  # SQLAlchemy ORM
│  ├─ schemas/                 # Pydantic DTO
│  ├─ db/                      # session / migrations
│  ├─ content_factory/         # 模板生成 + AI 改写
│  ├─ scheduler/               # APScheduler 周期 / Celery 队列
│  ├─ channels/
│  │  └─ xiaohongshu/          # 小红书适配器（首发）
│  └─ workers/                 # Celery 任务
├─ web/                        # 控制台前端（轻量 Jinja + 静态）
├─ deploy/
│  ├─ docker-compose.yml
│  ├─ Dockerfile
│  └─ nginx.conf
├─ scripts/                    # 初始化 / 烟测 / 抓 cookie 等
├─ tests/
├─ .env.example
├─ pyproject.toml
└─ README.md
```

---

## ⚙️ 配置

> 完整字段以仓库内 `.env.example` 为准；下表为速查。

| 分组 | 字段 | 默认 | 说明 |
| --- | --- | --- | --- |
| App | `APP_NAME` | `xhs-saas` | 应用名 |
| App | `APP_ENV` | `dev` | `dev` / `staging` / `prod` |
| App | `APP_HOST` | `0.0.0.0` | 监听地址 |
| App | `APP_PORT` | `8080` | 监听端口 |
| App | `APP_SECRET` | `change-me-please` | **生产请改**，用于签名 / cookie |
| DB | `DATABASE_URL` | `sqlite+aiosqlite:///./data/xhs_saas.db` | 生产建议 Postgres |
| Cache / MQ | `REDIS_URL` | `redis://redis:6379/0` | Celery broker + scheduler 锁 |
| Channel | `DEFAULT_CHANNEL` | `xiaohongshu` | 任务未指定渠道时的兜底 |
| Anti-detect | `HUMAN_DELAY_MIN_MS` | `1200` | 操作间最小随机延迟（毫秒） |
| Anti-detect | `HUMAN_DELAY_MAX_MS` | `4500` | 操作间最大随机延迟（毫秒） |
| Anti-detect | `PROXY_ROTATE_EVERY` | `20` | 每 N 次操作换一次代理 |
| Anti-detect | `WARMUP_HOURS_BEFORE_SOLOPOST` | `24` | 新号独立发帖前暖机时长 |
| Risk | `DAILY_POST_LIMIT_PER_ACCOUNT` | `5` | 单账号日发帖上限 |
| Risk | `HOURLY_POST_LIMIT_PER_ACCOUNT` | `2` | 单账号小时发帖上限 |
| Risk | `COOL_DOWN_MINUTES_AFTER_FAIL` | `30` | 失败后冷却分钟数 |
| AI | `OPENAI_API_KEY` | *空* | 内容改写；不填则跳过改写 |
| AI | `OPENAI_BASE_URL` | `https://api.openai.com/v1` | 兼容 OpenAI 协议的自建网关 |
| AI | `OPENAI_MODEL` | `gpt-4o-mini` | 改写模型 |
| Channels | `ENABLE_XIAOHONGSHU` | `true` | 启停小红书适配器 |
| Channels | `ENABLE_DOUYIN` | `false` | 启停抖音适配器 |
| Channels | `ENABLE_KUAISHOU` | `false` | 启停快手适配器 |

---

## 🚀 快速开始

### 方式 A：本地开发

```bash
# 1. 准备
cd xiaohongshu-saas
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev,ai]"
playwright install chromium

# 2. 配置
cp .env.example .env
# 编辑 .env，填 OPENAI_API_KEY（可选）等

# 3. 初始化数据库 + 启动
python -m scripts.init_db
uvicorn app.main:app --reload --port 8080

# 4. 另起终端，启动 worker
celery -A app.workers.celery_app worker -l info
```

打开 <http://localhost:8080>，默认账号 `admin` / `admin`（**首次登录后请立刻改密码**）。

### 方式 B：Docker 一键起

```bash
cd xiaohongshu-saas/deploy
docker compose up -d
# Web:  http://localhost:8080
# Prometheus: http://localhost:9090
```

### 方式 C：React 控制台（可选）

完整 React/Vite 管理界面，挂在 `/console`：

```bash
cd xiaohongshu-saas/web/console
npm install     # 或 pnpm install
npm run dev     # 开发模式 http://localhost:5173/console/
npm run build   # 打包到 dist/，之后 /console 由 FastAPI 直接服务
```

API 代理已配置，开发时 Vite 把 `/api` 请求转发到 `http://localhost:8080`。

---

## 🔑 小红书账号接入

> ⚠️ **合规提示**：请仅用于自有账号与授权内容，遵守小红书平台协议与所在地法律。

首次接入必须**人工扫码登录一次**，把 cookie 落地：

```bash
# 打开有头浏览器，扫码后 cookie 自动保存到 data/cookies/<account_id>.json
python scripts/harvest_xhs_cookie.py --account-id acc_001
```

之后 worker 会自动加载 cookie + 周期性刷新（接近过期时）。

---

## 🧩 一个最小"循环发帖"示例

通过控制台或 API 创建：

1. **账号** `acc_001`（已扫码）
2. **内容模板** `美瞳种草 v1`：标题前缀 + 5 个核心卖点 + 3 张配图 + 话题 `#美瞳推荐`
3. **任务** `loop_acc_001`：
   - 类型：`loop`（循环）
   - 间隔：`60 ± 15 分钟`
   - 时段：每天 09:00–22:00
   - 配额：日 5 条 / 小时 2 条
   - 启用 AI 改写：是

启动任务后，中台会按调度 → 内容工厂生成 → 风控校验 → 小红书适配器发布 → 回执入库 → 看板统计。

---

## 🌐 扩展到其他渠道

每个渠道只需实现 `app/channels/base.py` 里的接口：

```python
class ChannelAdapter(Protocol):
    name: str
    async def login(self, account: Account) -> None: ...
    async def publish(self, account: Account, content: ContentItem) -> PublishResult: ...
    async def heartbeat(self, account: Account) -> AccountHealth: ...
```

然后在中台注册：

```python
# app/channels/registry.py
register(XiaohongshuAdapter())
# register(DouyinAdapter())
# register(KuaishouAdapter())
```

即可在任务里选择渠道。

---

## 📊 观测

| 入口 | 用途 |
| --- | --- |
| `/metrics` | Prometheus 指标（任务成功率、平均延迟、队列长度） |
| `/api/dashboard/summary` | JSON 看板数据（账号数 / 今日发帖 / 失败率） |
| `logs/xhs-saas.log` | 结构化 JSON 日志（loguru） |
| `/api/health` | 健康检查（DB / Redis / 浏览器池） |

---

## 🛡️ 风控策略（默认，可调）

| 策略 | 默认值 | 配置项 |
| --- | --- | --- |
| 单账号日发帖上限 | 5 | `DAILY_POST_LIMIT_PER_ACCOUNT` |
| 单账号小时发帖上限 | 2 | `HOURLY_POST_LIMIT_PER_ACCOUNT` |
| 失败冷却 | 30 分钟 | `COOL_DOWN_MINUTES_AFTER_FAIL` |
| 人类化随机延迟 | 1.2–4.5 秒 | `HUMAN_DELAY_MIN_MS` / `_MAX_MS` |
| 代理轮换间隔 | 每 20 条 | `PROXY_ROTATE_EVERY` |
| 新号独立发帖前暖机时长 | 24 小时 | `WARMUP_HOURS_BEFORE_SOLOPOST` |

> 强烈建议：账号数量 × 单号日上限 < 平台安全阈值 + 30% 冗余。

---

## 🏗️ 部署指南

> 三种部署形态共存，按体量选。

### 1) 本机 / 内网 Docker（开发 / 小团队）

```bash
cd xiaohongshu-saas/deploy
cp ../.env.example .env && $EDITOR .env   # 改 APP_SECRET / OPENAI_API_KEY
docker compose up -d
docker compose ps
docker compose logs -f web worker
```

适用：≤ 10 账号、单实例、机器常驻。

### 2) 阿里云 ECS（生产推荐）

最小起步规格（**经验值，不是承诺**）：

| 角色 | 规格建议 | 说明 |
| --- | --- | --- |
| ECS（Web + Worker 同机） | 4 vCPU / 8 GiB / 80 GiB 系统盘 | 单机起步，浏览器池内存占用较高 |
| Redis | 1 GiB 托管 Redis 或自建 1 vCPU / 1 GiB | broker + scheduler lock |
| Postgres | 1 vCPU / 1 GiB / 20 GiB SSD | 任务回执 + 看板数据 |

要点：

- 安全组：仅放行 `8080`（Web）/ `9090`（Prometheus，可选内网）到可信 IP
- `APP_ENV=prod`、`APP_SECRET` 用密码管理器生成 32 字节随机
- `DATABASE_URL` 切到 Postgres；`REDIS_URL` 切到托管 Redis
- `nginx.conf` 已就绪，做 80/443 反代与 `/console` 静态
- 数据盘做**每日快照**（账户 / 内容 / 任务回执是关键资产）

### 3) 自有 K8s（多副本 / 高可用）

- `app.web` 至少 2 副本 + HPA（CPU 60%）
- `app.worker` 至少 2 副本，**注意**：浏览器池有状态，建议 StatefulSet + 节点亲和
- Redis / Postgres 用托管或 Operator；不要跑在浏览器池同节点
- Prometheus + Alertmanager 接入已有指标栈

---

## 🛠️ 运维

| 项 | 命令 / 路径 |
| --- | --- |
| 看 Web 日志（结构化） | `tail -F logs/xhs-saas.log` |
| 看 Worker 日志 | `docker compose logs -f worker` |
| 健康检查 | `curl localhost:8080/api/health` |
| 指标 | `curl localhost:8080/metrics` |
| 备份数据 | `pg_dump xhs_saas > backup_$(date +%F).sql` |
| 回滚 | `git checkout <tag> && docker compose up -d --build` |
| 改配置生效 | 改 `.env` 后 `docker compose up -d`（容器会读新 env） |
| 清 cookie 重登 | 删除 `data/cookies/<account_id>.json` 后跑 `harvest_xhs_cookie.py` |

---

## ❓ 常见问题（FAQ）

**Q1. 跑起来报 `playwright: command not found`。**
A: 先 `pip install -e ".[dev,ai]"`，再 `playwright install chromium`。

**Q2. Cookie 失效 / 任务一直 `auth_failed`。**
A: 删除对应账号的 `data/cookies/<id>.json`，重跑 `python scripts/harvest_xhs_cookie.py --account-id <id>` 人工扫码。

**Q3. Worker 报 `connection refused redis`。**
A: `REDIS_URL` 是否指向了 `redis:6379`（compose 网络名），本地直跑应改成 `redis://localhost:6379/0`。

**Q4. OpenAI 调用 401 / 超时。**
A: 检查 `OPENAI_API_KEY` 与 `OPENAI_BASE_URL`；不填 `OPENAI_API_KEY` 时**会**跳过改写，**不会**让任务失败。

**Q5. 任务数涨得快、账号被风控。**
A: 调小 `DAILY_POST_LIMIT_PER_ACCOUNT` / `HOURLY_POST_LIMIT_PER_ACCOUNT`；检查 `WARMUP_HOURS_BEFORE_SOLOPOST` 是否覆盖到新号。

**Q6. `/console` 404。**
A: 先 `npm run build` 产出 `web/console/dist/`，FastAPI 才会服务静态。

**Q7. Windows 下 Celery 起不来。**
A: Windows 原生不支持 Celery prefork；要么走 `docker compose`，要么把 worker 单独跑在 WSL / Linux。

---

## 🧪 测试

```bash
pytest -q
```

包含：内容工厂、风控、配额、调度状态机、适配器协议契约。

---

## 🗺️ 路线图

- [x] 中台骨架（账号 / 内容 / 任务 / 风控）
- [x] 小红书适配器（Playwright + cookie 复用）
- [x] 内容工厂（模板 + OpenAI 改写）
- [x] Docker 一键起
- [ ] 抖音 / 视频号适配器
- [ ] 多租户（团队 / 角色 / 计费）
- [ ] 移动端 H5 控制台
- [ ] 数据回流（曝光 / 互动 → 选题反哺）

---

## ⚖️ 免责声明

本项目仅用于**工程研究与自有账号自动化**，请：

1. 严格遵守各平台协议与机器人规范；
2. 不得用于刷量、灰产、虚假宣传等违规场景；
3. 因使用不当造成的封号、法律风险由使用者自行承担。

---

## 🆘 官方支持

- **Issues**：GitHub 仓库 `Issues` 区 — <https://github.com/zhenyu666-debug/xiaohongshu-Loop/issues>
- **维护状态**：个人项目，无 SLA，按 Issues 响应时间为准
- **联系方式**：默认仅 GitHub Issues（邮箱 / 微信 / 钉钉 等**未**配置 — 你**补**告诉我，我**改**）

---

## 📤 推送到你的 GitHub 仓库

```bash
cd xiaohongshu-saas
git init
git add .
git commit -m "feat: xhs-saas middle-platform scaffold (xiaohongshu first channel)"
git branch -M main
git remote add origin https://github.com/zhenyu666-debug/xiaohongshu-Loop.git
git push -u origin main
```

之后所有更新：

```bash
git add .
git commit -m "feat: ..."
git push
```

> 如果你用了 SSH key，把 `https://...` 换成 `git@github.com:zhenyu666-debug/xiaohongshu-Loop.git`。

---

## 📜 License

**MIT** — 仓库根 `LICENSE` 文件已落盘。

Copyright (c) 2026 zhenyu666-debug

允许任何人**免费**获取本软件副本，**不**受**限**地使用、复制、修改、合并、发布、分发、再授权 / 售卖，**前提**是**所有**副本 / 实质部分**保留**上述版权声明 + 本许可声明。

THE SOFTWARE IS PROVIDED "AS IS", **无**任何形式的明示 / 暗示担保。

---

> 你选了 MIT 是因为你**说**"全部优化至成功" = 授权代决。**换** Apache-2.0 / GPL-3.0 / AGPL-3.0 / All rights reserved, 你**说**一声我**换**。