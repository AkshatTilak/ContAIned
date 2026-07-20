"""add_agent_definitions

Revision ID: d1ea753fbd9d
Revises: a42f693903ac
Create Date: 2026-07-20 18:52:34.826846

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
"""add_agent_definitions

Revision ID: d1ea753fbd9d
Revises: a42f693903ac
Create Date: 2026-07-20 18:52:34.826846

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd1ea753fbd9d'
down_revision: Union[str, Sequence[str], None] = 'a42f693903ac'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('agent_definitions',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('role', sa.String(length=100), nullable=False),
    sa.Column('system_prompt', sa.Text(), nullable=False),
    sa.Column('model_id', sa.String(length=200), nullable=False),
    sa.Column('tools', sa.JSON(), nullable=True),
    sa.Column('temperature', sa.Float(), nullable=True),
    sa.Column('max_tokens', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_agent_definitions_name'), 'agent_definitions', ['name'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_agent_definitions_name'), table_name='agent_definitions')
    op.drop_table('agent_definitions')
