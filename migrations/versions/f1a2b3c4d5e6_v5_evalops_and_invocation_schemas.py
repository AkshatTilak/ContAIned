"""v5_evalops_and_invocation_schemas

Revision ID: f1a2b3c4d5e6
Revises: e9f1a2b3c4d5
Create Date: 2026-07-23 18:45:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, Sequence[str], None] = 'e9f1a2b3c4d5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema with expanded EvalRunHistory columns, EvalMetricResult, and AgentInvocationLog."""
    # 1. Expand eval_run_history table
    op.add_column('eval_run_history', sa.Column('recall_score', sa.Float(), nullable=True))
    op.add_column('eval_run_history', sa.Column('precision_score', sa.Float(), nullable=True))
    op.add_column('eval_run_history', sa.Column('context_recall_score', sa.Float(), nullable=True))
    op.add_column('eval_run_history', sa.Column('answer_relevance_score', sa.Float(), nullable=True))
    op.add_column('eval_run_history', sa.Column('hallucination_score', sa.Float(), nullable=True))
    op.add_column('eval_run_history', sa.Column('toxicity_score', sa.Float(), nullable=True))
    op.add_column('eval_run_history', sa.Column('bias_score', sa.Float(), nullable=True))
    op.add_column('eval_run_history', sa.Column('framework_used', sa.String(length=20), nullable=True))
    op.add_column('eval_run_history', sa.Column('total_test_cases', sa.Integer(), nullable=True))
    op.add_column('eval_run_history', sa.Column('passed_count', sa.Integer(), nullable=True))
    op.add_column('eval_run_history', sa.Column('failed_count', sa.Integer(), nullable=True))

    # 2. Create eval_metric_results table
    op.create_table(
        'eval_metric_results',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('run_id', sa.String(length=36), nullable=False),
        sa.Column('test_case_id', sa.String(length=36), nullable=True),
        sa.Column('metric_name', sa.String(length=100), nullable=False),
        sa.Column('metric_score', sa.Float(), nullable=True),
        sa.Column('metric_reason', sa.Text(), nullable=True),
        sa.Column('framework', sa.String(length=20), nullable=False),
        sa.Column('threshold', sa.Float(), nullable=True),
        sa.Column('passed', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['run_id'], ['eval_run_history.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['test_case_id'], ['eval_test_cases.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_eval_metric_results_run_id'), 'eval_metric_results', ['run_id'], unique=False)
    op.create_index(op.f('ix_eval_metric_results_test_case_id'), 'eval_metric_results', ['test_case_id'], unique=False)

    # 3. Create agent_invocation_log table
    op.create_table(
        'agent_invocation_log',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('agent_id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('prompt', sa.Text(), nullable=False),
        sa.Column('response', sa.Text(), nullable=True),
        sa.Column('model_used', sa.String(length=200), nullable=True),
        sa.Column('input_tokens', sa.Integer(), nullable=True),
        sa.Column('output_tokens', sa.Integer(), nullable=True),
        sa.Column('latency_ms', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True, server_default='success'),
        sa.Column('route_decision', sa.String(length=50), nullable=True),
        sa.Column('metadata_json', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['agent_id'], ['agent_definitions.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_agent_invocation_log_agent_id'), 'agent_invocation_log', ['agent_id'], unique=False)
    op.create_index(op.f('ix_agent_invocation_log_user_id'), 'agent_invocation_log', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_agent_invocation_log_user_id'), table_name='agent_invocation_log')
    op.drop_index(op.f('ix_agent_invocation_log_agent_id'), table_name='agent_invocation_log')
    op.drop_table('agent_invocation_log')

    op.drop_index(op.f('ix_eval_metric_results_test_case_id'), table_name='eval_metric_results')
    op.drop_index(op.f('ix_eval_metric_results_run_id'), table_name='eval_metric_results')
    op.drop_table('eval_metric_results')

    op.drop_column('eval_run_history', 'failed_count')
    op.drop_column('eval_run_history', 'passed_count')
    op.drop_column('eval_run_history', 'total_test_cases')
    op.drop_column('eval_run_history', 'framework_used')
    op.drop_column('eval_run_history', 'bias_score')
    op.drop_column('eval_run_history', 'toxicity_score')
    op.drop_column('eval_run_history', 'hallucination_score')
    op.drop_column('eval_run_history', 'answer_relevance_score')
    op.drop_column('eval_run_history', 'context_recall_score')
    op.drop_column('eval_run_history', 'precision_score')
    op.drop_column('eval_run_history', 'recall_score')
