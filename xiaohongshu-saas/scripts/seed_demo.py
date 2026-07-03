"""Seed a demo account + demo loop task."""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from app.db.session import init_db, session_scope
from app.models import Account, Task


async def main() -> None:
    Path("data/templates").mkdir(parents=True, exist_ok=True)

    sample_tmpl = {
        "key": "beauty_瞳_v1",
        "title_prefix": "今日瞳",
        "body": "今天这副 {emoji} 是新宠！自然扩瞳又不会死板 · {hour} 点钟自然光下更温柔。\n喜欢的姐妹评论区扣 1 ✨",
        "topics": ["#美瞳推荐", "#日常妆容"],
        "images": [],
        "extra": {"category": "beauty"},
    }
    Path("data/templates/beauty_瞳_v1.json").write_text(
        json.dumps(sample_tmpl, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    await init_db()
    async with session_scope() as session:
        if not await session.get(Account, "acc_001"):
            session.add(Account(
                id="acc_001",
                channel="xiaohongshu",
                nickname="瞳瞳日报",
                stage="warmup",
                warmup_until=datetime.utcnow() + timedelta(hours=24),
            ))
        if not await session.get(Task, 1):
            session.add(Task(
                name="瞳瞳日报 · 循环",
                channel="xiaohongshu",
                account_ids=["acc_001"],
                template_key="beauty_瞳_v1",
                kind="loop",
                status="draft",
                interval_minutes=60,
                jitter_minutes=15,
                window_start="09:00",
                window_end="22:00",
                use_ai=False,
            ))
    print("OK: seeded.")