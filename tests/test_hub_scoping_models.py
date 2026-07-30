from common.models import Base, HUB_SCOPED_MODELS, INHERITED_SCOPE_TABLES
from projects.syntraflow.src.database.models import SyntraFlowCollection, build_physical_name


def test_hub_scoped_models_registry():
    """Assert HUB_SCOPED_MODELS contains exactly the 12 NOT NULL tables from hubs.md §3.6 and S6-06a."""
    expected_tables = {
        "agent_definitions",
        "agent_invocation_log",
        "workflows",
        "workflow_runs",
        "eval_test_suites",
        "eval_run_history",
        "eval_flow_traces",
        "syntraflow_collections",
        "syntraflow_documents",
        "syntraflow_chunks",
        "syntraflow_video_segments",
        "syntraflow_jobs",
    }
    assert set(HUB_SCOPED_MODELS.keys()) == expected_tables

    for table_name, model_cls in HUB_SCOPED_MODELS.items():
        assert getattr(model_cls, "__hub_scoped__", False) is True
        table = Base.metadata.tables[table_name]
        assert "hub_id" in table.columns
        col = table.columns["hub_id"]
        assert col.nullable is False
        assert len(col.foreign_keys) == 1
        fk = next(iter(col.foreign_keys))
        assert fk.target_fullname == "hubs.id"


def test_optional_hub_scoped_models():
    """Assert api_keys, mcp_servers, and playground_sessions have nullable hub_id."""
    optional_tables = ["api_keys", "mcp_servers", "playground_sessions"]
    for table_name in optional_tables:
        table = Base.metadata.tables[table_name]
        assert "hub_id" in table.columns
        col = table.columns["hub_id"]
        assert col.nullable is True
        assert len(col.foreign_keys) == 1
        fk = next(iter(col.foreign_keys))
        assert fk.target_fullname == "hubs.id"


def test_inherited_scope_tables():
    """Assert INHERITED_SCOPE_TABLES mapping contains all inherited models."""
    expected_inherited = {
        "eval_test_cases": ("suite_id", "eval_test_suites"),
        "eval_metric_results": ("run_id", "eval_run_history"),
        "mcp_tool_cache": ("server_id", "mcp_servers"),
        "workflow_versions": ("workflow_id", "workflows"),
    }
    assert INHERITED_SCOPE_TABLES == expected_inherited


def test_syntraflow_collection_schema():
    """Assert SyntraFlowCollection schema updates (no tenant_id, physical_name present)."""
    table = Base.metadata.tables["syntraflow_collections"]
    assert "tenant_id" not in table.columns
    assert "physical_name" in table.columns
    assert hasattr(SyntraFlowCollection, "physical_name")
    assert not hasattr(SyntraFlowCollection, "tenant_id")


def test_build_physical_name_helper():
    """Assert build_physical_name constructs canonical {hub_slug}__{name} string."""
    assert build_physical_name("support_kb", "faqs") == "support_kb__faqs"


def test_composite_unique_constraints_exist():
    """Assert expected composite unique constraints exist in Base.metadata."""
    all_constraints = set()
    for table in Base.metadata.tables.values():
        for const in table.constraints:
            if hasattr(const, "name") and const.name:
                all_constraints.add(const.name)

    expected_constraint_names = {
        "uq_agent_definitions_hub_slug",
        "uq_syntraflow_collections_hub_name",
        "uq_syntraflow_collections_physical_name",
        "uq_workflows_hub_slug",
        "uq_eval_test_suites_hub_name",
    }
    assert expected_constraint_names.issubset(all_constraints)
