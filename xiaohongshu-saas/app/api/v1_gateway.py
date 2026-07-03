"""HTTP gateway router for upstream services (pbp-api, lakehouse-api).

GET  /api/v1/{short}/{path:path}      -> proxies to upstream
GET  /api/v1/health/all               -> aggregate self + upstreams health
GET  /api/v1/cache/clear              -> clear cached upstream responses (admin)
"""
from __future__ import annotations

import time
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request

from app.core.cache import health_cache
from app.core.config import settings

router = APIRouter(prefix="/api/v1", tags=["gateway"])

_UPSTREAM_TIMEOUT = 5.0
_UPSTREAM_PATHS: dict[str, tuple[str, str]] = {
    # short -> (upstream base, mount path under /api/v1/{short})
    "pbp": (settings.pbp_api_url, "/api"),
    "lakehouse": (settings.lakehouse_api_url, "/api"),
}


async def _proxy(short: str, request: Request, path: str) -> Any:
    if short not in _UPSTREAM_PATHS:
        raise HTTPException(status_code=404, detail=f"unknown upstream '{short}'")
    base, mount = _UPSTREAM_PATHS[short]
    target = f"{base.rstrip('/')}{mount}/{path}".rstrip("/")
    if request.url.query:
        target += f"?{request.url.query}"
    body = await request.body() if request.method in {"POST", "PUT", "PATCH"} else None
    try:
        async with httpx.AsyncClient(timeout=_UPSTREAM_TIMEOUT) as client:
            r = await client.request(request.method, target, content=body)
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"upstream {short} unreachable: {e!s}") from e
    if r.status_code >= 400:
        raise HTTPException(status_code=r.status_code, detail=r.text)
    return r.json() if r.headers.get("content-type", "").startswith("application/json") else r.text


async def _probe_one(client: httpx.AsyncClient, name: str, base: str, health_path: str) -> dict:
    started = time.perf_counter()
    try:
        r = await client.get(f"{base.rstrip('/')}{health_path}", timeout=_UPSTREAM_TIMEOUT)
        latency = round((time.perf_counter() - started) * 1000, 1)
        return {"name": name, "status": "up" if r.is_success else "down", "latency_ms": latency}
    except httpx.RequestError:
        return {"name": name, "status": "down", "latency_ms": None}


@router.get("/health/all")
async def health_all() -> dict:
    """Aggregate health for self + upstream services (3s TTL cache)."""
    cached = health_cache.get("health/all")
    if cached:
        cached["cache_hit"] = True
        return cached
    tasks = []
    async with httpx.AsyncClient() as client:
        # self
        tasks.append(_probe_one(client, "xhs-saas", f"http://localhost:{settings.app_port}", "/api/healthz"))
        for short, (base, _mount) in _UPSTREAM_PATHS.items():
            tasks.append(_probe_one(client, short, base, "/healthz"))
        services = await __await_gather(tasks)
    statuses = {s["status"] for s in services}
    overall = "ok" if statuses == {"up"} else ("down" if statuses == {"down"} else "degraded")
    out = {"status": overall, "services": services, "cache_hit": False}
    health_cache.set("health/all", out)
    return out


async def __await_gather(coros):
    import asyncio
    return await asyncio.gather(*coros)


@router.post("/cache/clear")
async def cache_clear() -> dict:
    """Clear all gateway caches. Useful for manual upstream refresh."""
    health_cache.invalidate()
    return {"cleared": True, "remaining_size": health_cache.size()}


@router.get("/cache/stats")
async def cache_stats() -> dict:
    return {
        "health_cache_size": health_cache.size(),
        "health_cache_ttl_seconds": health_cache._ttl,
    }


# Catch-all proxy routes registered LAST so /health/all etc. resolve first.
def _make_proxy_handler(short: str):
    async def _handler(request: Request, path: str = "") -> Any:
        return await _proxy(short, request, path)
    return _handler


for short_name in _UPSTREAM_PATHS:
    router.add_api_route(
        f"/{short_name}/{{path:path}}",
        _make_proxy_handler(short_name),
        methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    )