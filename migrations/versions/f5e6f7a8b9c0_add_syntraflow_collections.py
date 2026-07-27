"""add_syntraflow_collections

Revision ID: f5e6f7a8b9c0
Revises: f4d5e6f7a8b9
Create Date: 2026-07-27 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f5e6f7a8b9c0'
down_revision: Union[str, Sequence[str], None] = 'f4d5e6f7a8b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create syntraflow_collections table."""
    op.create_table(
        'syntraflow_collections',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('tenant_id', sa.String(length=255), nullable=False, server_default='default'),
        sa.Column('embedding_model', sa.String(length=255), nullable=False, server_default='jina-clip-v2'),
        sa.Column('vector_dimension', sa.Integer(), nullable=False, server_default='1024'),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index(op.f('ix_syntraflow_collections_name'), 'syntraflow_collections', ['name'], unique=True)


def downgrade() -> None:
    """Drop syntraflow_collections table."""
    op.drop_index(op.f('ix_syntraflow_collections_name'), table_name='syntraflow_collections')
    op.drop_table('syntraflow_collections')
