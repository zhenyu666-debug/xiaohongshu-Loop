"""FastAPI app factory."""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from pbp_api.routers import candidates, health

app = FastAPI(
    title="pbp-api",
    description="donor-screener-pbp candidate scoring API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(candidates.router, prefix="/api")