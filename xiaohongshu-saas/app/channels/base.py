"""Channel adapter interface (Protocol)."""
from __future__ import annotations

from typing import Protocol

from app.core.types import AccountHealth, ContentItem, PublishResult
from app.models import Account


class ChannelAdapter(Protocol):
    """Implement this for each new social platform."""

    name: str

    async def login(self, account: Account) -> None: ...

    async def publish(self, account: Account, content: ContentItem) -> PublishResult: ...

    async def heartbeat(self, account: Account) -> AccountHealth: ...