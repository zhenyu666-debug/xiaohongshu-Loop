from typing import Literal

from fastapi import APIRouter, Query

from lakehouse_api import client

router = APIRouter()


@router.get("/kpis")
async def get_kpis() -> dict:
    """Top-level KPIs for today: PV, UV, PV/UV ratio, conversions, funnel."""
    return client.kpis()


@router.get("/funnel")
async def get_funnel() -> dict:
    return {"items": client.funnel()}


@router.get("/series/{name}")
async def get_series(name: Literal["pv", "uv", "conversions"], days: int = Query(14, ge=2, le=90)) -> dict:
    return client.series(name, days)


@router.get("/top-items")
async def get_top_items(metric: Literal["pv", "uv", "conversions"] = "pv", limit: int = Query(10, ge=2, le=50)) -> dict:
    return {"metric": metric, "items": client.top_items(metric, limit)}