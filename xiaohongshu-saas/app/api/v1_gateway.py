"""HTTP gateway router for upstream services (pbp-api, lakehouse-api).

Forwards /api/v1/{pbp,lakehouse}/* to upstream URLs configured in
`Settings.pbp_api_url` / `Settings.lakehouse_api_url`. Each upstream is
probed concurrently on `/api/v1/health/all` so the GUI's HealthBadge can
surface per-service status.

The gateway is intentionally thin: it does not cache, validate, or
transform payloads beyond injecting CORS-friendly error envelopes.
Authentication / rate-limiting belong to the upstream services.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

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
    return JSONResponse(content=r.json(), status_code=r.status_code, headers={"x-upstream": short})


async def _probe_one(client: httpx.AsyncClient, name: str, base: str, health_path: str) -> dict:
    started = time.perf_counter()
    try:
        r = await client.get(f"{base.rstrip('/')}{health_path}", timeout=_UPSTREAM_TIMEOUT)
        latency = round((time.perf_counter() - started) * 1000, 1)
        return {"name": name, "status": "up" if r.is_success else "down", "latency_ms": latency}
    except httpx.RequestError:
        return {"name": name, "status": "down"}


@router.get("/health/all")
async def health_all() -> dict:
    """Aggregate health for self + upstream services."""
    tasks = []
    async with httpx.AsyncClient() as client:
        # self
        tasks.append(_probe_one(client, "xhs-saas", f"http://localhost:{settings.app_port}", "/api/healthz"))
        for short, (base, _mount) in _UPSTREAM_PATHS.items():
            tasks.append(_probe_one(client, short, base, "/healthz"))
        results = await asyncio.gather(*tasks, return_exceptions=False)
    up = sum(1 for r in results if r["status"] == "up")
    overall = "ok" if up == len(results) else ("degraded" if up > 0 else "down")
    return {"status": overall, "services": results}


# Catch-all proxy: /api/v1/{short}/{path:path}
@router.api_route(
    "/{short}/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    include_in_schema=False,
)
async def catch_all(short: str, path: str, request: Request) -> Any:
    return await _proxy(short, request, path)


# Root-level short cut (e.g. /api/v1/pbp/healthz)
@router.api_route(
    "/{short}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    include_in_schema=False,
)
async def catch_short(short: str, request: Request) -> Any:
    return await _proxy(short, request, "")