"""API router aggregator."""
from fastapi import APIRouter

from app.api import accounts, misc, tasks, v1_gateway
api_router = APIRouter()
api_router.include_router(accounts.router)
api_router.include_router(tasks.router)
api_router.include_router(misc.router)
api_router.include_router(v1_gateway.router)
