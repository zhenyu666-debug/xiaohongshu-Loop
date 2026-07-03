"""Structured logging via loguru."""
from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from app.core.config import settings

_LOG_DIR = Path("logs")
_LOG_DIR.mkdir(parents=True, exist_ok=True)


def setup_logging() -> None:
    logger.remove()
    logger.add(
        sys.stderr,
        level="DEBUG" if settings.app_env == "dev" else "INFO",
        colorize=True,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
    )
    logger.add(
        _LOG_DIR / "xhs-saas.log",
        level="INFO",
        rotation="20 MB",
        retention="14 days",
        enqueue=True,
        serialize=True,
    )


__all__ = ["logger", "setup_logging"]