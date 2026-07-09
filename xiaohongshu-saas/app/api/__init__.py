"""API router aggregator."""
from fastapi import APIRouter

from app.api import accounts, ai, alerts, auth, billing, events, misc, tasks, tenants, v1_gateway

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(tenants.router)
api_router.include_router(billing.router)
api_router.include_router(accounts.router)
api_router.include_router(tasks.router)
api_router.include_router(misc.router)
api_router.include_router(alerts.router)
api_router.include_router(events.router)
api_router.include_router(v1_gateway.router)
api_router.include_router(ai.router)