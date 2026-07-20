"""add_eval_attribution_tables

Revision ID: 85e2f0c51f71
Revises: 7d3140d819a9
Create Date: 2026-07-20 19:16:05.895343

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
"""add_eval_attribution_tables

Revision ID: 85e2f0c51f71
Revises: 7d3140d819a9
Create Date: 2026-07-20 19:16:05.895343

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '85e2f0c51f71'
down_revision: Union[str, Sequence[str], None] = '7d3140d819a9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('eval_test_suites',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('agent_id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('description', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['agent_id'], ['agent_definitions.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_eval_test_suites_agent_id'), 'eval_test_suites', ['agent_id'], unique=False)

    op.create_table('eval_run_history',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('agent_id', sa.String(length=36), nullable=False),
    sa.Column('suite_id', sa.String(length=36), nullable=True),
    sa.Column('faithfulness_score', sa.Float(), nullable=True),
    sa.Column('relevance_score', sa.Float(), nullable=True),
    sa.Column('duration_sec', sa.Float(), nullable=True),
    sa.Column('run_status', sa.String(length=32), nullable=False),
    sa.Column('details_json', sa.JSON(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['agent_id'], ['agent_definitions.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['suite_id'], ['eval_test_suites.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_eval_run_history_agent_id'), 'eval_run_history', ['agent_id'], unique=False)
    op.create_index(op.f('ix_eval_run_history_suite_id'), 'eval_run_history', ['suite_id'], unique=False)

    op.create_table('eval_test_cases',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('suite_id', sa.String(length=36), nullable=False),
    sa.Column('input_query', sa.Text(), nullable=False),
    sa.Column('expected_output', sa.Text(), nullable=True),
    sa.Column('expected_context', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['suite_id'], ['eval_test_suites.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_eval_test_cases_suite_id'), 'eval_test_cases', ['suite_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_eval_test_cases_suite_id'), table_name='eval_test_cases')
    op.drop_table('eval_test_cases')
    op.drop_index(op.f('ix_eval_run_history_suite_id'), table_name='eval_run_history')
    op.drop_index(op.f('ix_eval_run_history_agent_id'), table_name='eval_run_history')
    op.drop_table('eval_run_history')
    op.drop_index(op.f('ix_eval_test_suites_agent_id'), table_name='eval_test_suites')
    op.drop_table('eval_test_suites')
