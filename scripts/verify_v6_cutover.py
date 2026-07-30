#!/usr/bin/env python3
"""Cutover Verification Script for V6 Hub Architecture (S6-11e).

Scans repository files to ensure no forbidden V5 legacy symbols, flat routes,
obsolete components, or stale platform roles re-enter the codebase outside documentation.
"""

import argparse
import fnmatch
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

@dataclass
class Rule:
    name: str
    pattern: str
    kind: str  # "literal" or "regex"
    reason: str
    allowed_paths: List[str]

DEFAULT_EXCLUDES = [
    "agent_buildable_base/**",
    "migrations/versions/**",
    "**/__pycache__/**",
    "frontend/node_modules/**",
    "frontend/dist/**",
    ".git/**",
    ".venv/**",
    "scripts/verify_v6_cutover.py",
    "scripts/tests/**",
    "tests/**",
    "**/tests/**",
]

FORBIDDEN_RULES: List[Rule] = [
    Rule(
        name="legacy_agent_routes",
        pattern=r'"/api/agents',
        kind="literal",
        reason="Flat /api/agents route decommissioned; use /api/hubs/{hub_id}/agents",
        allowed_paths=[],
    ),
    Rule(
        name="legacy_syntraflow_routes",
        pattern=r'"/api/syntraflow',
        kind="literal",
        reason="Flat /api/syntraflow route decommissioned; use /api/hubs/{hub_id}/ingestion",
        allowed_paths=[],
    ),
    Rule(
        name="legacy_evalops_routes",
        pattern=r'"/api/evalops',
        kind="literal",
        reason="Flat /api/evalops route decommissioned; use /api/hubs/{hub_id}/eval",
        allowed_paths=[],
    ),
    Rule(
        name="legacy_mcp_hub_naming",
        pattern=r"MCP Integration Hub|MCP Hub",
        kind="regex",
        reason="Renamed to 'MCP Registry'",
        allowed_paths=[],
    ),
    Rule(
        name="legacy_v5_components",
        pattern=r"\b(AgentHub|WorkflowCanvas|IngestionPanel|EvalPanel|CollectionManager|UserManagement|PropertyDrawer)\.tsx",
        kind="regex",
        reason="Legacy flat V5 component files decommissioned",
        allowed_paths=[],
    ),
]


def is_excluded(path_str: str, excludes: List[str]) -> bool:
    norm_path = path_str.replace("\\", "/")
    for pattern in excludes:
        if fnmatch.fnmatch(norm_path, pattern) or fnmatch.fnmatch(os.path.basename(norm_path), pattern):
            return True
        if pattern.endswith("/**") and norm_path.startswith(pattern[:-3]):
            return True
    return False


def run_verification(root_dir: Path, include_docs: bool = False) -> int:
    excludes = [] if include_docs else DEFAULT_EXCLUDES
    violations = 0

    for path in root_dir.glob("**/*"):
        if not path.is_file():
            continue

        rel_path = str(path.relative_to(root_dir)).replace("\\", "/")
        if is_excluded(rel_path, excludes):
            continue

        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for line_num, line in enumerate(content.splitlines(), start=1):
            for rule in FORBIDDEN_RULES:
                matched = False
                if rule.kind == "literal":
                    matched = rule.pattern in line
                elif rule.kind == "regex":
                    matched = bool(re.search(rule.pattern, line))

                if matched:
                    # Check if file is explicitly allowed for this rule
                    if any(fnmatch.fnmatch(rel_path, ap) for ap in rule.allowed_paths):
                        continue

                    print(f"{rel_path}:{line_num}: [{rule.name}] {rule.reason}")
                    violations += 1

    if violations > 0:
        print(f"\n[FAIL] Cutover verification failed with {violations} violation(s).")
        return 1
    else:
        print("\n[SUCCESS] Cutover verification passed cleanly! 0 legacy V5 violations found.")
        return 0


def main():
    parser = argparse.ArgumentParser(description="Verify V6 Cutover Rule Compliance")
    parser.add_argument("--include-docs", action="store_true", help="Include documentation trees in check")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    sys.exit(run_verification(repo_root, include_docs=args.include_docs))


if __name__ == "__main__":
    main()
