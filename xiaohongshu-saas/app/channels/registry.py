"""Channel registry."""
from __future__ import annotations

from typing import Dict

from app.channels.base import ChannelAdapter
from app.core.errors import ChannelNotEnabled
from app.core.logging import logger


_REGISTRY: Dict[str, ChannelAdapter] = {}


def register(adapter: ChannelAdapter) -> None:
    _REGISTRY[adapter.name] = adapter
    logger.info("Channel registered: {}", adapter.name)


def get(name: str) -> ChannelAdapter:
    if name not in _REGISTRY:
        raise ChannelNotEnabled(f"channel '{name}' not registered")
    return _REGISTRY[name]


def all_names() -> list[str]:
    return list(_REGISTRY.keys())


def bootstrap() -> None:
    """Auto-register channels based on settings."""
    from app.core.config import settings
    from app.channels.xiaohongshu.adapter import XiaohongshuAdapter
    from app.channels.douyin.adapter import DouyinAdapter

    if settings.enable_xiaohongshu:
        register(XiaohongshuAdapter())
    if settings.enable_douyin:
        try:
            register(DouyinAdapter())
        except Exception as exc:  # noqa: BLE001
            logger.warning("Douyin adapter failed to register: {}", exc)