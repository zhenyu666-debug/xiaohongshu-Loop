"""API router aggregator."""
from fastapi import APIRouter

from app.api import accounts, misc, tasks

api_router = APIRouter()
api_router.include_router(accounts.router)
api_router.include_router(tasks.router)
api_router.include_router(misc.router)