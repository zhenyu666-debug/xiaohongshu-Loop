"""Seed MGU PhD probe account + task for account 676072139."""
from __future__ import annotations
import asyncio
from pathlib import Path
from sqlalchemy import select
from app.db.session import init_db, session_scope
from app.models import Account, Task

ACCOUNT_ID   = "acc_676072139"
TASK_NAME    = "莫大博士招生 · 限流探测"
TEMPLATE_KEY = "mgu_phd"

async def main() -> None:
    Path("data/templates").mkdir(parents=True, exist_ok=True)
    await init_db()
    async with session_scope() as s:
        acc = await s.get(Account, ACCOUNT_ID)
        if acc is None:
            s.add(Account(
                id=ACCOUNT_ID, channel="xiaohongshu", nickname="卡匹迪恩",
                stage="normal", enabled=True,
                cookie_path=f"data/cookies/{ACCOUNT_ID}.json",
            ))
            print(f"Account {ACCOUNT_ID} created.")
        else:
            print(f"Account {ACCOUNT_ID} exists (stage={acc.stage}).")
        existing = (await s.execute(select(Task).where(Task.name == TASK_NAME))).scalar_one_or_none()
        if existing is None:
            s.add(Task(
                name=TASK_NAME, channel="xiaohongshu", account_ids=[ACCOUNT_ID],
                template_key=TEMPLATE_KEY, kind="probe", status="draft",
                interval_minutes=30, window_start="08:00", window_end="23:00", use_ai=False,
            ))
            print(f'Task "{TASK_NAME}" created.')
        else:
            print(f'Task "{TASK_NAME}" exists, updating...')
            existing.kind = "probe"
            existing.account_ids = [ACCOUNT_ID]
            existing.template_key = TEMPLATE_KEY
            existing.interval_minutes = 30
    async with session_scope() as s:
        acc = await s.get(Account, ACCOUNT_ID)
        task = (await s.execute(select(Task).where(Task.name == TASK_NAME))).scalar_one_or_none()
        print()
        print("=== Seed summary ===")
        print(f"  Account: {acc.id} stage={acc.stage} enabled={acc.enabled}")
        ck = acc.cookie_path or ""
        print(f"  Cookie file: {ck} exists={Path(ck).exists() if ck else False}")
        print(f"  Task id={task.id} kind={task.kind} status={task.status}")
        if not (ck and Path(ck).exists()):
            print()
            print(f"WARNING: cookie missing. Run: python -m scripts.harvest_xhs_cookie --account-id {ACCOUNT_ID}")
        print("OK")

if __name__ == "__main__":
    asyncio.run(main())
