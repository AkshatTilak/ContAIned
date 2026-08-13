
import pytest
pytestmark = pytest.mark.unit
"""Static AST Query Guard Test (S6-02e).

Walks Python files under gateway/ and projects/ to ensure no unscoped queries against
__hub_scoped__ models are authored without an explicit allowlist entry.
"""

import ast
from pathlib import Path
import pytest

from common.models import HUB_SCOPED_MODELS

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ALLOWLIST_FILE = PROJECT_ROOT / "tests" / "hub_query_guard_allowlist.txt"


def load_allowlist():
    if not ALLOWLIST_FILE.exists():
        return set()
    entries = set()
    with open(ALLOWLIST_FILE, "r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if not line_str or line_str.startswith("#"):
                continue
            if "#" not in line_str:
                pytest.fail(f"Allowlist entry '{line_str}' is missing mandatory '# reason' comment")
            entry = line_str.split("#")[0].strip()
            entries.add(entry)
    return entries


def get_target_python_files():
    dirs_to_check = [PROJECT_ROOT / "gateway", PROJECT_ROOT / "projects"]
    files = []
    for d in dirs_to_check:
        if d.exists():
            files.extend(d.rglob("*.py"))
    return files


def test_hub_query_guard():
    allowlist = load_allowlist()
    hub_scoped_names = set(HUB_SCOPED_MODELS.keys())
    # Also add class names
    for cls in HUB_SCOPED_MODELS.values():
        hub_scoped_names.add(cls.__name__)

    violations = []
    target_files = get_target_python_files()

    for py_file in target_files:
        rel_path = py_file.relative_to(PROJECT_ROOT).as_posix()
        try:
            source = py_file.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=rel_path)
        except Exception:
            continue

        for node in ast.walk(tree):
            # Check for session.get(HubScopedModel, ...)
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute) and node.func.attr == "get":
                    if node.args and isinstance(node.args[0], ast.Name) and node.args[0].id in hub_scoped_names:
                        loc = f"{rel_path}:{node.lineno}"
                        if not any(loc.startswith(entry.split("::")[0]) for entry in allowlist):
                            violations.append(f"{loc} -> session.get({node.args[0].id}, ...)")

    assert not violations, "Unscoped hub model query violations found:\n" + "\n".join(violations)
