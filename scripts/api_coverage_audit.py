"""FastAPI API Coverage Audit Script (B8-16 / sub_16_07).

Inspects all registered routes in Gateway FastAPI app and verifies test coverage across test suite.
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple

# Set env before importing app
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("AUTH_ENABLED", "false")


def collect_app_routes() -> List[Tuple[str, str, str]]:
    """Enumerate all registered routes (method, path, endpoint_name) from OpenAPI schema."""
    try:
        from gateway.main import app
    except Exception as e:
        print(f"Failed to import gateway app: {e}")
        return []

    openapi_schema = app.openapi()
    paths = openapi_schema.get("paths", {})

    routes = []
    for path, methods in paths.items():
        for method, operation in methods.items():
            if method.upper() not in ("HEAD", "OPTIONS"):
                summary = operation.get("summary") or operation.get("operationId", "")
                routes.append((method.upper(), path, summary))

    return sorted(routes, key=lambda x: (x[1], x[0]))


def collect_tested_paths(tests_dir: Path) -> Set[str]:
    """Extract tested URL paths from test files."""
    tested_patterns = set()
    url_pattern = re.compile(r'["\'](/api/[^"\']+|/v1/[^"\']+|/health|/auth/[^"\']+|/qdrant[^"\']*)["\']')

    for py_file in tests_dir.rglob("*.py"):
        content = py_file.read_text(encoding="utf-8", errors="ignore")
        for match in url_pattern.finditer(content):
            tested_patterns.add(match.group(1))

    return tested_patterns


def match_route_to_tested(path: str, tested_paths: Set[str]) -> bool:
    """Check if route pattern matches any tested path."""
    clean_path = path.rstrip("/")
    if clean_path in tested_paths or path in tested_paths:
        return True

    # Normalize path parameters e.g. /api/hubs/{id} vs /api/hubs/123
    norm_pattern = re.sub(r"\{[^}]+\}", r"[^/]+", path)
    regex = re.compile(f"^{norm_pattern}$")
    for t_path in tested_paths:
        # Strip query params
        t_base = t_path.split("?")[0].rstrip("/")
        if regex.match(t_base):
            return True
    return False


def run_audit():
    root = Path(__file__).resolve().parent.parent
    tests_dir = root / "tests"

    routes = collect_app_routes()
    tested_paths = collect_tested_paths(tests_dir)

    print(f"\n{'='*70}")
    print(f"           CONTAiNED API SURFACE COVERAGE AUDIT")
    print(f"{'='*70}\n")

    tested_count = 0
    untested_count = 0

    print(f"{'METHOD':<8} {'PATH':<50} {'STATUS':<10}")
    print(f"{'-'*8} {'-'*50} {'-'*10}")

    for method, path, name in routes:
        is_covered = match_route_to_tested(path, tested_paths)
        if is_covered:
            status_str = "[TESTED]"
            tested_count += 1
        else:
            status_str = "[UNTESTED]"
            untested_count += 1

        print(f"{method:<8} {path:<50} {status_str:<10}")

    total = tested_count + untested_count
    cov_pct = (tested_count / total * 100) if total > 0 else 0

    print(f"\n{'-'*70}")
    print(f"Total Routes: {total} | Covered: {tested_count} | Untested: {untested_count} | Coverage: {cov_pct:.1f}%")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    run_audit()
