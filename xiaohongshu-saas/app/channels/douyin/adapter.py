"""Douyin (TikTok China) channel adapter (skeleton).

This module mirrors the structure of the Xiaohongshu adapter but is intentionally
left as a stub. The web UI selectors for ``creator.douyin.com`` are volatile, so
each method raises ``NotImplementedError`` until the actual flow is implemented.

To enable: set ``ENABLE_DOUYIN=true`` in ``.env`` and implement the three methods.
"""
from __future__ import annotations

from pathlib import Path

from app.channels.base import ChannelAdapter
from app.core.logging import logger
from app.core.types import AccountHealth, ContentItem, PublishResult
from app.models import Account


_LOGIN_URL = "https://creator.douyin.com/"
_PUBLISH_URL = "https://creator.douyin.com/creator-micro/home?enter_from=publish"

_COOKIE_DIR = Path("data/cookies")


class DouyinAdapter(ChannelAdapter):
    name = "douyin"

    def __init__(self) -> None:
        self._cookie_dir = _COOKIE_DIR
        self._cookie_dir.mkdir(parents=True, exist_ok=True)

    def cookie_path_for(self, account_id: str) -> Path:
        path = self._cookie_dir / f"{account_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    async def login(self, account: Account) -> None:
        raise NotImplementedError(
            "DouyinAdapter.login is not implemented yet. "
            "Drive creator.douyin.com QR scan via Playwright, then persist cookies "
            "to adapter.cookie_path_for(account.id) and set account.cookie_path."
        )

    async def publish(self, account: Account, content: ContentItem) -> PublishResult:
        logger.warning("douyin adapter stub hit for publish (account={})", account.id)
        raise NotImplementedError(
            "DouyinAdapter.publish is not implemented yet. "
            "Use the selectors in app/channels/douyin/selectors.py as a starting point."
        )

    async def heartbeat(self, account: Account) -> AccountHealth:
        raise NotImplementedError(
            "DouyinAdapter.heartbeat is not implemented yet. "
            "Navigate to creator home and check for login redirect."
        )