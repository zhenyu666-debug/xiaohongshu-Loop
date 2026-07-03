"""Manually harvest Xiaohongshu cookies by scanning the QR code once.

Usage:
    python -m scripts.harvest_xhs_cookie --account-id acc_001 [--proxy http://user:pass@host:port]
"""
from __future__ import annotations

import argparse
import asyncio

from app.channels import registry as channel_registry
from app.channels.xiaohongshu.adapter import XiaohongshuAdapter
from app.core.config import settings
from app.db.session import init_db, session_scope
from app.models import Account


async def main(account_id: str, proxy: str | None) -> None:
    settings.app_env = "dev"  # ensure headed browser for QR scan
    channel_registry.bootstrap()
    await init_db()

    async with session_scope() as session:
        account = await session.get(Account, account_id)
        if not account:
            account = Account(
                id=account_id,
                channel="xiaohongshu",
                nickname=account_id,
                proxy=proxy,
                stage="new",
            )
            session.add(account)
        else:
            account.proxy = proxy

    adapter: XiaohongshuAdapter = channel_registry.get("xiaohongshu")  # type: ignore
    async with session_scope() as session:
        account = await session.get(Account, account_id)
        assert account is not None
        await adapter.login(account)
        account.stage = "warmup"
        account.cookie_path = str(adapter.cookie_path_for(account.id))
    print(f"OK: account {account_id} logged in. cookies -> {adapter.cookie_path_for(account_id)}")
    await adapter.shutdown()


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--account-id", required=True)
    p.add_argument("--proxy", default=None)
    args = p.parse_args()
    asyncio.run(main(args.account_id, args.proxy))