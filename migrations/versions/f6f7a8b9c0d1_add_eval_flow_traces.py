"""add_eval_flow_traces

Revision ID: f6f7a8b9c0d1
Revises: f5e6f7a8b9c0
Create Date: 2026-07-27 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6f7a8b9c0d1'
down_revision: Union[str, Sequence[str], None] = 'f5e6f7a8b9c0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create eval_flow_traces table."""
    op.create_table(
        'eval_flow_traces',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('run_id', sa.String(length=36), sa.ForeignKey('eval_run_history.id', ondelete='CASCADE'), nullable=True),
        sa.Column('workflow_id', sa.String(length=100), nullable=True),
        sa.Column('node_id', sa.String(length=100), nullable=False),
        sa.Column('node_type', sa.String(length=50), nullable=False),
        sa.Column('input_state', sa.JSON(), nullable=True),
        sa.Column('output_state', sa.JSON(), nullable=True),
        sa.Column('latency_ms', sa.Float(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_eval_flow_traces_run_id'), 'eval_flow_traces', ['run_id'], unique=False)
    op.create_index(op.f('ix_eval_flow_traces_workflow_id'), 'eval_flow_traces', ['workflow_id'], unique=False)


def downgrade() -> None:
    """Drop eval_flow_traces table."""
    op.drop_index(op.f('ix_eval_flow_traces_workflow_id'), table_name='eval_flow_traces')
    op.drop_index(op.f('ix_eval_flow_traces_run_id'), table_name='eval_flow_traces')
    op.drop_table('eval_flow_traces')
