"""add ai_mode to tasks table.

Revision ID: 0003_ai_mode
Revises: 0002_tenant_id
Create Date: 2026-07-10 14:30:00.000000

Task.ai_mode controls how AI is used during publishing:
- rewrite (default): factory.maybe_rewrite() – single prompt, fast
- agent: CoordinatorAgent.coordinate_task() – multi-step planning + fan-out

The column is idempotent: upgrade skips when column exists;
downgrade uses IF EXISTS (SQLite 3.35+).

"""
from typing import Sequence, Union

from alembic import op


revision: str = "0003_ai_mode"
down_revision: Union[str, None] = "0002_tenant_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_exists(table: str, column: str) -> bool:
    result = op.get_bind().execute(
        __import__("sqlalchemy").text(f"PRAGMA table_info({table})")
    )
    return any(row[1] == column for row in result)


def upgrade() -> None:
    if not _column_exists("tasks", "ai_mode"):
        op.execute(
            "ALTER TABLE tasks ADD COLUMN ai_mode VARCHAR(32) DEFAULT 'rewrite'"
        )


def downgrade() -> None:
    if _column_exists("tasks", "ai_mode"):
        # SQLite 3.35+ DROP COLUMN is always idempotent
        op.execute("ALTER TABLE tasks DROP COLUMN IF EXISTS ai_mode")