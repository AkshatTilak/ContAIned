"""v6_eval_hub_polymorphic_targets

Revision ID: e3f4a5b6c7d8
Revises: e2f3a4b5c6d7
Create Date: 2026-07-30 12:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e3f4a5b6c7d8'
down_revision: Union[str, Sequence[str], None] = 'e2f3a4b5c6d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(name: str) -> bool:
    return name in _inspector().get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    if not _has_table(table_name):
        return False
    columns = [c["name"] for c in _inspector().get_columns(table_name)]
    return column_name in columns


def upgrade() -> None:
    bind = op.get_bind()
    is_sqlite = bind.dialect.name == "sqlite"

    # 1. eval_test_suites polymorphic & hub columns
    if _has_table("eval_test_suites"):
        if not _has_column("eval_test_suites", "hub_id"):
            if is_sqlite:
                op.add_column("eval_test_suites", sa.Column("hub_id", sa.String(36), nullable=True))
            else:
                op.add_column("eval_test_suites", sa.Column("hub_id", sa.String(36), sa.ForeignKey("hubs.id", ondelete="CASCADE"), nullable=True))
            op.create_index(op.f("ix_eval_test_suites_hub_id"), "eval_test_suites", ["hub_id"], unique=False)
        if not _has_column("eval_test_suites", "target_type"):
            op.add_column("eval_test_suites", sa.Column("target_type", sa.String(20), nullable=True, server_default="agent"))
        if not _has_column("eval_test_suites", "target_hub_id"):
            if is_sqlite:
                op.add_column("eval_test_suites", sa.Column("target_hub_id", sa.String(36), nullable=True))
            else:
                op.add_column("eval_test_suites", sa.Column("target_hub_id", sa.String(36), sa.ForeignKey("hubs.id", ondelete="RESTRICT"), nullable=True))
            op.create_index(op.f("ix_eval_test_suites_target_hub_id"), "eval_test_suites", ["target_hub_id"], unique=False)
        if not _has_column("eval_test_suites", "target_id"):
            op.add_column("eval_test_suites", sa.Column("target_id", sa.String(36), nullable=True))
            op.create_index(op.f("ix_eval_test_suites_target_id"), "eval_test_suites", ["target_id"], unique=False)

        existing_unique = [u["name"] for u in _inspector().get_unique_constraints("eval_test_suites")]
        if "uq_eval_test_suites_hub_name" in existing_unique:
            try:
                op.drop_constraint("uq_eval_test_suites_hub_name", "eval_test_suites", type_="unique")
            except Exception:
                pass
        if "uq_eval_suites_hub_name" not in existing_unique:
            try:
                op.create_unique_constraint("uq_eval_suites_hub_name", "eval_test_suites", ["hub_id", "name"])
            except Exception:
                pass

    # 2. eval_run_history polymorphic & hub columns
    if _has_table("eval_run_history"):
        if not _has_column("eval_run_history", "hub_id"):
            if is_sqlite:
                op.add_column("eval_run_history", sa.Column("hub_id", sa.String(36), nullable=True))
            else:
                op.add_column("eval_run_history", sa.Column("hub_id", sa.String(36), sa.ForeignKey("hubs.id", ondelete="CASCADE"), nullable=True))
            op.create_index(op.f("ix_eval_run_history_hub_id"), "eval_run_history", ["hub_id"], unique=False)
        if not _has_column("eval_run_history", "target_type"):
            op.add_column("eval_run_history", sa.Column("target_type", sa.String(20), nullable=True, server_default="agent"))
        if not _has_column("eval_run_history", "target_hub_id"):
            if is_sqlite:
                op.add_column("eval_run_history", sa.Column("target_hub_id", sa.String(36), nullable=True))
            else:
                op.add_column("eval_run_history", sa.Column("target_hub_id", sa.String(36), sa.ForeignKey("hubs.id", ondelete="RESTRICT"), nullable=True))
            op.create_index(op.f("ix_eval_run_history_target_hub_id"), "eval_run_history", ["target_hub_id"], unique=False)
        if not _has_column("eval_run_history", "target_id"):
            op.add_column("eval_run_history", sa.Column("target_id", sa.String(36), nullable=True))
            op.create_index(op.f("ix_eval_run_history_target_id"), "eval_run_history", ["target_id"], unique=False)
        if not _has_column("eval_run_history", "workflow_run_id"):
            if is_sqlite:
                op.add_column("eval_run_history", sa.Column("workflow_run_id", sa.String(36), nullable=True))
            else:
                op.add_column("eval_run_history", sa.Column("workflow_run_id", sa.String(36), sa.ForeignKey("workflow_runs.id", ondelete="SET NULL"), nullable=True))
            op.create_index(op.f("ix_eval_run_history_workflow_run_id"), "eval_run_history", ["workflow_run_id"], unique=False)

    # 3. eval_test_cases node assertion columns
    if _has_table("eval_test_cases"):
        if not _has_column("eval_test_cases", "node_id"):
            op.add_column("eval_test_cases", sa.Column("node_id", sa.String(100), nullable=True))
            op.create_index(op.f("ix_eval_test_cases_node_id"), "eval_test_cases", ["node_id"], unique=False)
        if not _has_column("eval_test_cases", "assertion_type"):
            op.add_column("eval_test_cases", sa.Column("assertion_type", sa.String(30), nullable=True))
        if not _has_column("eval_test_cases", "assertion_config"):
            op.add_column("eval_test_cases", sa.Column("assertion_config", sa.JSON(), nullable=True))
        if not _has_column("eval_test_cases", "expected_value"):
            op.add_column("eval_test_cases", sa.Column("expected_value", sa.Text(), nullable=True))

    # 4. eval_metric_results node assertion columns
    if _has_table("eval_metric_results"):
        if not _has_column("eval_metric_results", "node_id"):
            op.add_column("eval_metric_results", sa.Column("node_id", sa.String(100), nullable=True))
            op.create_index(op.f("ix_eval_metric_results_node_id"), "eval_metric_results", ["node_id"], unique=False)
        if not _has_column("eval_metric_results", "assertion_type"):
            op.add_column("eval_metric_results", sa.Column("assertion_type", sa.String(30), nullable=True))


def downgrade() -> None:
    if _has_table("eval_metric_results"):
        if _has_column("eval_metric_results", "assertion_type"):
            op.drop_column("eval_metric_results", "assertion_type")
        if _has_column("eval_metric_results", "node_id"):
            op.drop_index(op.f("ix_eval_metric_results_node_id"), table_name="eval_metric_results")
            op.drop_column("eval_metric_results", "node_id")

    if _has_table("eval_test_cases"):
        for col in ["expected_value", "assertion_config", "assertion_type"]:
            if _has_column("eval_test_cases", col):
                op.drop_column("eval_test_cases", col)
        if _has_column("eval_test_cases", "node_id"):
            op.drop_index(op.f("ix_eval_test_cases_node_id"), table_name="eval_test_cases")
            op.drop_column("eval_test_cases", "node_id")

    if _has_table("eval_run_history"):
        existing_indexes = [i["name"] for i in _inspector().get_indexes("eval_run_history")]
        for col in ["workflow_run_id", "target_id", "target_hub_id", "hub_id"]:
            idx_name = f"ix_eval_run_history_{col}"
            if idx_name in existing_indexes:
                try:
                    op.drop_index(idx_name, table_name="eval_run_history")
                except Exception:
                    pass
        with op.batch_alter_table("eval_run_history") as batch_op:
            for col in ["workflow_run_id", "target_id", "target_hub_id", "target_type", "hub_id"]:
                if _has_column("eval_run_history", col):
                    batch_op.drop_column(col)

    if _has_table("eval_test_suites"):
        existing_unique = [u["name"] for u in _inspector().get_unique_constraints("eval_test_suites")]
        if "uq_eval_suites_hub_name" in existing_unique:
            try:
                op.drop_constraint("uq_eval_suites_hub_name", "eval_test_suites", type_="unique")
            except Exception:
                pass
        existing_indexes = [i["name"] for i in _inspector().get_indexes("eval_test_suites")]
        for col in ["target_id", "target_hub_id", "hub_id"]:
            idx_name = f"ix_eval_test_suites_{col}"
            if idx_name in existing_indexes:
                try:
                    op.drop_index(idx_name, table_name="eval_test_suites")
                except Exception:
                    pass
        with op.batch_alter_table("eval_test_suites") as batch_op:
            for col in ["target_id", "target_hub_id", "target_type", "hub_id"]:
                if _has_column("eval_test_suites", col):
                    batch_op.drop_column(col)
