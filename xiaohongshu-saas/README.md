# xiaohongshu-Loop · 小红书起步的多渠道 SaaS 中台 · 自动发帖机器人

> 一个面向**多账号 / 多渠道**社媒运营的 SaaS 中台，**首发渠道：小红书**。后续可平滑扩展到抖音、快手、视频号、B 站、知乎等。
> 核心思路：把"账号池 · 内容工厂 · 调度器 · 渠道适配器 · 风控"解耦，做一个可观测、可灰度的中台骨架。

---

## ✨ 亮点

- **中台架构**：账号 / 内容 / 任务 / 风控 / 渠道五层解耦，业务侧只关心"什么账号发什么内容什么时间发"。
- **小红书首发**：内置 Playwright 适配器，支持图文 / 视频笔记、话题、@、位置，定时与循环。
- **内容工厂**：内置模板生成 + 可选 OpenAI 改写，支持多账号人设差异化。
- **风控优先**：账号分级（新号→冷启→正常）、日 / 小时配额、失败冷却、人类化随机延迟、代理轮换。
- **可观测**：结构化日志（loguru）、任务状态机、Prometheus 指标、健康检查。
- **易部署**：`docker-compose up` 一键拉起 Web + Worker + Redis + Postgres。

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

- `/metrics`     Prometheus 指标（任务成功率、平均延迟、队列长度）
- `/api/dashboard/summary` JSON 看板数据（账号数 / 今日发帖 / 失败率）
- `logs/xhs-saas.log` 结构化 JSON 日志

---

## 🛡️ 风控策略（默认，可调）

| 策略                         | 默认值              | 配置项                          |
|------------------------------|---------------------|---------------------------------|
| 单账号日发帖上限             | 5                   | `DAILY_POST_LIMIT_PER_ACCOUNT`  |
| 单账号小时发帖上限           | 2                   | `HOURLY_POST_LIMIT_PER_ACCOUNT` |
| 失败冷却                     | 30 分钟             | `COOL_DOWN_MINUTES_AFTER_FAIL`  |
| 人类化随机延迟               | 1.2–4.5 秒          | `HUMAN_DELAY_MIN_MS` / `_MAX_MS` |
| 代理轮换间隔                 | 每 20 条            | `PROXY_ROTATE_EVERY`            |
| 新号独立发帖前暖机时长       | 24 小时             | `WARMUP_HOURS_BEFORE_SOLOPOST`  |

> 强烈建议：账号数量 × 单号日上限 < 平台安全阈值 + 30% 冗余。

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