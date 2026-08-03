"""v7_soft_deletion_columns

Revision ID: g7a8b9c0d1e2
Revises: e4f5a6b7c8d9
Create Date: 2026-08-03 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'g7a8b9c0d1e2'
down_revision: Union[str, Sequence[str], None] = 'e4f5a6b7c8d9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _inspector():
    return sa.inspect(op.get_bind())


def _has_column(table: str, column: str) -> bool:
    insp = _inspector()
    if not insp.has_table(table):
        return False
    columns = [c['name'] for c in insp.get_columns(table)]
    return column in columns


def upgrade() -> None:
    """Add is_deleted and deleted_at columns to users and hubs tables."""
    if not _has_column('users', 'is_deleted'):
        op.add_column('users', sa.Column('is_deleted', sa.Boolean(), server_default='0', nullable=False))
        op.create_index(op.f('ix_users_is_deleted'), 'users', ['is_deleted'], unique=False)
    if not _has_column('users', 'deleted_at'):
        op.add_column('users', sa.Column('deleted_at', sa.DateTime(), nullable=True))

    if not _has_column('hubs', 'is_deleted'):
        op.add_column('hubs', sa.Column('is_deleted', sa.Boolean(), server_default='0', nullable=False))
        op.create_index(op.f('ix_hubs_is_deleted'), 'hubs', ['is_deleted'], unique=False)
    if not _has_column('hubs', 'deleted_at'):
        op.add_column('hubs', sa.Column('deleted_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Drop soft deletion columns from users and hubs tables."""
    if _has_column('hubs', 'deleted_at'):
        op.drop_column('hubs', 'deleted_at')
    if _has_column('hubs', 'is_deleted'):
        op.drop_index(op.f('ix_hubs_is_deleted'), table_name='hubs')
        op.drop_column('hubs', 'is_deleted')

    if _has_column('users', 'deleted_at'):
        op.drop_column('users', 'deleted_at')
    if _has_column('users', 'is_deleted'):
        op.drop_index(op.f('ix_users_is_deleted'), table_name='users')
        op.drop_column('users', 'is_deleted')
