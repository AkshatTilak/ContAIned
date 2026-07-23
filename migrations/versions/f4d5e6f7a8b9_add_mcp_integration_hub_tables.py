"""add_mcp_integration_hub_tables

Revision ID: f4d5e6f7a8b9
Revises: f3c4d5e6f7a8
Create Date: 2026-07-24 00:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f4d5e6f7a8b9'
down_revision: Union[str, Sequence[str], None] = 'f3c4d5e6f7a8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create mcp_servers and mcp_tool_cache tables."""
    op.create_table(
        'mcp_servers',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('url', sa.String(length=500), nullable=False),
        sa.Column('transport', sa.String(length=30), nullable=False, server_default='sse'),
        sa.Column('auth_type', sa.String(length=20), nullable=True, server_default='none'),
        sa.Column('auth_token_encrypted', sa.Text(), nullable=True),
        sa.Column('is_internal', sa.Boolean(), nullable=True, server_default=sa.text('0')),
        sa.Column('is_active', sa.Boolean(), nullable=True, server_default=sa.text('1')),
        sa.Column('health_status', sa.String(length=20), nullable=True, server_default='unknown'),
        sa.Column('last_health_check', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )

    op.create_table(
        'mcp_tool_cache',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('server_id', sa.String(length=36), nullable=False),
        sa.Column('tool_name', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('input_schema_json', sa.JSON(), nullable=True),
        sa.Column('is_enabled', sa.Boolean(), nullable=True, server_default=sa.text('1')),
        sa.Column('last_synced', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['server_id'], ['mcp_servers.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_mcp_tool_cache_server_id'), 'mcp_tool_cache', ['server_id'], unique=False)


def downgrade() -> None:
    """Drop mcp_tool_cache and mcp_servers tables."""
    op.drop_index(op.f('ix_mcp_tool_cache_server_id'), table_name='mcp_tool_cache')
    op.drop_table('mcp_tool_cache')
    op.drop_table('mcp_servers')
