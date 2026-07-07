"""baseline: stamp current schema at revision 0001.

This is a STAMP-ONLY baseline. No DDL is executed on upgrade or downgrade.

Why stamp-only?
- The dev DB (data/xhs_saas.db) has been brought up by init_db() /
  Base.metadata.create_all for several revisions.
- Forcing a full create_table chain now would fail because every table
  already exists in the DB.
- A no-op baseline lets alembic stamp head succeed without backfilling
  data, and any future schema change can be added as a new revision
  on top of this head.

If you ever wipe the DB, run init_db() first (which recreates all
tables), then alembic stamp head to mark this baseline as applied.

Revision ID: 0001_baseline
Revises:
Create Date: 2026-07-07 09:25:00.000000

"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by alembic.
revision: str = "0001_baseline"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """No-op stamp. The current schema is captured by alembic_version."""
    pass


def downgrade() -> None:
    """No-op. Use alembic stamp base to clear."""
    pass