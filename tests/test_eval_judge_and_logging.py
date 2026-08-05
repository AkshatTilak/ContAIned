"""Unit tests for EvalOps Judge Resolver & Trace Logging (sub_09_01 & sub_09_02)."""

import pytest
from projects.evalops.src.runner.judge_resolver import resolve_judge_model


@pytest.mark.asyncio
async def test_resolve_judge_model_fallback():
    judge = await resolve_judge_model("completion")
    assert isinstance(judge, str)
    assert len(judge) > 0
