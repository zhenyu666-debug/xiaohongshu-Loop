"""FastAPI application entrypoint."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from app.api import api_router
from app.channels import registry as channel_registry
from app.core.config import settings
from app.core.logging import logger, setup_logging
from app.core import metrics
from app.db.session import init_db
from app.scheduler import shutdown_scheduler, start_scheduler


WEB_DIR = Path(__file__).resolve().parent.parent / "web"


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    channel_registry.bootstrap()
    await init_db()
    start_scheduler()
    logger.info("xhs-saas started, env={}", settings.app_env)
    try:
        yield
    finally:
        shutdown_scheduler()
        xhs = channel_registry.get("xiaohongshu") if "xiaohongshu" in channel_registry.all_names() else None
        if xhs and hasattr(xhs, "shutdown"):
            await xhs.shutdown()


app = FastAPI(
    title="xhs-saas",
    description="Multi-channel social-media SaaS middleware, starting with Xiaohongshu.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)
metrics.install_fastapi_app(app)


# ---- Web console (lightweight Jinja-free fallback) ----
if (WEB_DIR / "static").exists():
    app.mount("/static", StaticFiles(directory=WEB_DIR / "static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    """Minimal console homepage. Replace with full Jinja/React UI as needed."""
    html = """<!doctype html>
<html lang=zh>
<head>
<meta charset=utf-8>
<title>xhs-saas 控制台</title>
<style>
  body { font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif; margin: 0; background:#0f172a; color:#e2e8f0; }
  header { padding: 24px; background:#111827; border-bottom: 1px solid #1f2937; }
  h1 { margin:0; font-size: 20px; }
  main { display:grid; grid-template-columns: repeat(4, 1fr); gap: 16px; padding: 24px; }
  .card { background:#111827; border:1px solid #1f2937; border-radius: 12px; padding: 16px; }
  .card h3 { margin:0 0 8px 0; font-size:13px; color:#94a3b8; font-weight:500; }
  .card .v { font-size: 28px; font-weight:700; color:#22d3ee; }
  a.btn { display:inline-block; padding:8px 12px; background:#22d3ee; color:#0f172a;
         border-radius: 8px; text-decoration:none; font-weight:600; margin-right:8px; }
  table { width:100%; border-collapse: collapse; margin-top: 16px; }
  th,td { text-align:left; padding:8px 12px; border-bottom:1px solid #1f2937; font-size:13px; }
  th { color:#94a3b8; font-weight:500; }
  .pill { padding:2px 8px; border-radius: 999px; font-size:11px; background:#1e293b; }
  .ok { background:#064e3b; color:#6ee7b7; }
  .fail { background:#7f1d1d; color:#fca5a5; }
</style>
</head>
<body>
<header>
  <h1>🚀 xhs-saas · 小红书优先的多渠道中台</h1>
  <p style="margin:6px 0 0;color:#94a3b8;font-size:13px">
    首发渠道：xiaohongshu · 骨架：账号池 / 内容工厂 / 调度 / 风控 / 渠道适配器
  </p>
</header>
<main>
  <div class=card><h3>账号总数</h3><div class=v id=kpi-accounts>—</div></div>
  <div class=card><h3>活跃账号</h3><div class=v id=kpi-active>—</div></div>
  <div class=card><h3>进行中任务</h3><div class=v id=kpi-tasks>—</div></div>
  <div class=card><h3>今日发布</h3><div class=v id=kpi-pub>—</div></div>
</main>
<section style="padding:0 24px 24px">
  <div>
    <a class=btn href="/docs">API 文档</a>
    <a class=btn href="/api/dashboard/summary">看板 JSON</a>
  </div>
  <h3 style="margin-top:24px;color:#94a3b8">最近发布</h3>
  <table>
    <thead><tr><th>时间</th><th>账号</th><th>渠道</th><th>状态</th><th>标题</th></tr></thead>
    <tbody id=pubs></tbody>
  </table>
</section>
<script>
async function load() {
  const s = await (await fetch('/api/dashboard/summary')).json();
  document.getElementById('kpi-accounts').textContent = s.accounts_total;
  document.getElementById('kpi-active').textContent = s.accounts_active;
  document.getElementById('kpi-tasks').textContent = s.tasks_active;
  document.getElementById('kpi-pub').textContent = s.published_today;
  const pubs = await (await fetch('/api/publishes?limit=20')).json();
  document.getElementById('pubs').innerHTML = pubs.map(p => `
    <tr>
      <td>${(p.created_at || '').replace('T',' ').slice(0,19)}</td>
      <td>${p.account_id}</td>
      <td>${p.channel}</td>
      <td><span class="pill ${p.status==='success'?'ok':(p.status==='failed'?'fail':'')}">${p.status}</span></td>
      <td>${(p.title || '').slice(0,40)}</td>
    </tr>`).join('');
}
load(); setInterval(load, 8000);
</script>
</body></html>"""
    return HTMLResponse(html)


@app.get("/healthz")
async def root_healthz() -> dict:
    return {"status": "ok"}


@app.get("/favicon.ico")
async def favicon():
    return RedirectResponse(url="/static/favicon.ico")