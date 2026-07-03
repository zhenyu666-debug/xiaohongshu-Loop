"""Initialize SQLite DB (dev convenience). For prod use Alembic."""
from __future__ import annotations

import asyncio

from app.db.session import init_db


async def main() -> None:
    await init_db()
    print("OK: tables created.")


if __name__ == "__main__":
    asyncio.run(main())