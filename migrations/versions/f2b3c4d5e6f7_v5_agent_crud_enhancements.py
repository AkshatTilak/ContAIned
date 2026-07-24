"""v5_agent_crud_enhancements

Revision ID: f2b3c4d5e6f7
Revises: f1a2b3c4d5e6
Create Date: 2026-07-23 23:51:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f2b3c4d5e6f7'
down_revision: Union[str, Sequence[str], None] = 'f1a2b3c4d5e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add is_active and endpoint_slug to agent_definitions."""
    op.add_column('agent_definitions', sa.Column('is_active', sa.Boolean(), server_default=sa.text('true'), nullable=False))
    op.add_column('agent_definitions', sa.Column('endpoint_slug', sa.String(length=100), nullable=True))
    op.create_index(op.f('ix_agent_definitions_is_active'), 'agent_definitions', ['is_active'], unique=False)
    op.create_index(op.f('ix_agent_definitions_endpoint_slug'), 'agent_definitions', ['endpoint_slug'], unique=True)


def downgrade() -> None:
    """Remove is_active and endpoint_slug from agent_definitions."""
    op.drop_index(op.f('ix_agent_definitions_endpoint_slug'), table_name='agent_definitions')
    op.drop_index(op.f('ix_agent_definitions_is_active'), table_name='agent_definitions')
    op.drop_column('agent_definitions', 'endpoint_slug')
    op.drop_column('agent_definitions', 'is_active')
