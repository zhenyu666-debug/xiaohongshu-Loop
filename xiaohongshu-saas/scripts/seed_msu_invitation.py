"""Seed an account + one-shot task for the MSU PhD invitation template.

Usage (from xiaohongshu-saas/):
    python -m scripts.seed_msu_invitation
    python -m scripts.seed_msu_invitation --account-id msu-test --print-task-id

After running, trigger the publish with:
    curl -X POST http://127.0.0.1:8080/api/tasks/<task_id>/run
"""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from sqlalchemy import select

from app.core.config import settings
from app.db.session import init_db, session_scope
from app.models import Account, Task


TEMPLATE_PATH = Path("data/templates/msu_invitation_zh.json")
TEMPLATE_KEY = "msu_invitation_zh"
DEFAULT_ACCOUNT_ID = "msu-test"
TASK_NAME = "MSU 博士招生邀请 - one-shot"


# Body inlined so the seeder is the single tracked source of truth.
# `data/templates/*.json` is git-ignored by xiaohongshu-saas/.gitignore:16,
# matching the seed_demo.py convention.
TEMPLATE_SPEC: dict = {
    "key": TEMPLATE_KEY,
    "title_prefix": "莫斯科国立大学 博士招生",
    "body": (
        "收到一封来自 🇷🇺 莫斯科国立大学（MSU）的全奖博士邀请，正式渠道发出。\n"
        "\n"
        "—— 基本信息 ——\n"
        "· 学校：Lomonosov Moscow State University\n"
        "· 方向：{emoji}\n"
        "· 资助：全额奖学金 + 住宿 + 医疗保险\n"
        "· 学制：4 年（PhD）\n"
        "· 开学：{hour} 月入学（可沟通）\n"
        "\n"
        "—— 为什么值得关注 ——\n"
        "1. 莫斯科国立大学是俄罗斯排名第一的研究型大学，QS 学科覆盖广。\n"
        "2. 全奖覆盖学费、生活费，符合条件者还能申请额外科研补贴。\n"
        "3. 学校可协助办理俄罗斯长期学生签证。\n"
        "4. 英文授课项目较多，俄语零基础也可申请。\n"
        "\n"
        "—— 适合人群 ——\n"
        "· 想拿全奖读博、预算有限的本科 / 硕士应届生。\n"
        "· 想体验欧亚文化、做跨境科研的同学。\n"
        "· 对材料、化学、物理、数学、信息技术等基础学科有兴趣的同学。\n"
        "\n"
        "—— 申请建议 ——\n"
        "· 提前准备 CV、动机信、本硕成绩单、2 封推荐信。\n"
        "· 若有 SCI 论文或者竞赛奖项，会显著加分。\n"
        "· 套磁邮件尽量具体到导师组，避免群发模板。\n"
        "\n"
        "—— 我的下一步 ——\n"
        "我打算先联系导师组确认研究方向和名额，再启动签证准备流程。\n"
        "有同样在申请欧洲 / 俄罗斯方向博士的同学，欢迎在评论区交流 🙏\n"
        "\n"
        "（注：本文为个人收到的招生邀请整理，不构成任何商业推荐；具体名额与资助细节"
        "以导师组官方回复为准。）"
    ),
    "topics": ["#莫斯科国立大学", "#博士申请", "#留学"],
    "images": [],
    "extra": {"category": "education", "language": "zh"},
}


def _ensure_template_on_disk() -> None:
    """Write the template JSON on first run, then leave it alone.

    Matches seed_demo.py: the seeder is the tracked source of truth, the
    on-disk JSON is the cache. Subsequent runs re-use the existing file.
    """
    TEMPLATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not TEMPLATE_PATH.exists():
        TEMPLATE_PATH.write_text(
            json.dumps(TEMPLATE_SPEC, ensure_ascii=False, indent=2), encoding="utf-8"
        )


async def _seed(account_id: str, print_only: bool) -> int:
    _ensure_template_on_disk()
    await init_db()
    task_id: int = -1
    tenant_id = settings.default_tenant_id

    async with session_scope() as session:
        account = await session.get(Account, account_id)
        if account is None:
            session.add(
                Account(
                    id=account_id,
                    tenant_id=tenant_id,
                    channel="xiaohongshu",
                    nickname="MSU invite test",
                    stage="warmup",
                )
            )
        else:
            account.nickname = "MSU invite test"
            account.stage = "warmup"

        rows = (
            await session.execute(
                select(Task).where(Task.tenant_id == tenant_id, Task.channel == "xiaohongshu")
            )
        ).scalars().all()
        existing = next((t for t in rows if t.name == TASK_NAME), None)

        if existing is None:
            task = Task(
                tenant_id=tenant_id,
                name=TASK_NAME,
                channel="xiaohongshu",
                account_ids=[account_id],
                template_key=TEMPLATE_KEY,
                kind="once",
                status="paused",
                interval_minutes=None,
                use_ai=False,
            )
            session.add(task)
            await session.flush()
            task_id = task.id
        else:
            existing.template_key = TEMPLATE_KEY
            existing.account_ids = [account_id]
            existing.kind = "once"
            existing.status = "paused"
            task_id = existing.id

    print(f"OK: account '{account_id}' + task_id={task_id} ready (template={TEMPLATE_KEY}).")
    if print_only:
        print(
            json.dumps(
                {"task_id": task_id, "account_id": account_id, "template_key": TEMPLATE_KEY},
                ensure_ascii=False,
            )
        )
    return task_id


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--account-id", default=DEFAULT_ACCOUNT_ID)
    p.add_argument("--print-task-id", action="store_true")
    args = p.parse_args()
    asyncio.run(_seed(args.account_id, args.print_task_id))


if __name__ == "__main__":
    main()