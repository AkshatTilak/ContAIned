"""v6_agent_hub_backfill

Revision ID: e0f1a2b3c4d5
Revises: d9e0f1a2b3c4
Create Date: 2026-07-29 18:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e0f1a2b3c4d5'
down_revision: Union[str, Sequence[str], None] = 'd9e0f1a2b3c4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()

    # 1. Backfill agent_definitions.hub_id
    conn.execute(
        sa.text(
            """
            UPDATE agent_definitions
            SET hub_id = COALESCE(
                hub_id,
                (SELECT id FROM hubs WHERE hub_type='agent' AND slug='default' LIMIT 1),
                '00000000-0000-0000-0000-000000000002'
            )
            WHERE hub_id IS NULL;
            """
        )
    )
    op.alter_column("agent_definitions", "hub_id", nullable=False)

    # 2. Backfill agent_invocation_log.hub_id
    conn.execute(
        sa.text(
            """
            UPDATE agent_invocation_log
            SET hub_id = COALESCE(
                hub_id,
                (SELECT hub_id FROM agent_definitions WHERE id = agent_invocation_log.agent_id),
                (SELECT id FROM hubs WHERE hub_type='agent' AND slug='default' LIMIT 1),
                '00000000-0000-0000-0000-000000000002'
            )
            WHERE hub_id IS NULL;
            """
        )
    )
    op.alter_column("agent_invocation_log", "hub_id", nullable=False)


def downgrade() -> None:
    pass
