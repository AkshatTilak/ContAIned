"""add_playground_sessions

Revision ID: f3c4d5e6f7a8
Revises: f2b3c4d5e6f7
Create Date: 2026-07-24 00:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f3c4d5e6f7a8'
down_revision: Union[str, Sequence[str], None] = 'f2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create playground_sessions table."""
    op.create_table(
        'playground_sessions',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('model_id', sa.String(length=200), nullable=True),
        sa.Column('system_prompt', sa.Text(), nullable=True),
        sa.Column('messages_json', sa.JSON(), nullable=False),
        sa.Column('attachments_json', sa.JSON(), nullable=True),
        sa.Column('temperature', sa.Float(), nullable=True),
        sa.Column('max_tokens', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_playground_sessions_user_id'), 'playground_sessions', ['user_id'], unique=False)


def downgrade() -> None:
    """Drop playground_sessions table."""
    op.drop_index(op.f('ix_playground_sessions_user_id'), table_name='playground_sessions')
    op.drop_table('playground_sessions')
