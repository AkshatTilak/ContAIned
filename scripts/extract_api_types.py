"""Extract TypeScript interfaces from frontend/src/types/api.ts into JSON Schema definitions.

Used by contract tests in tests/e2e/contracts/ to validate backend API responses against frontend types.
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


def parse_ts_type(ts_type_str: str) -> Dict[str, Any]:
    """Map TypeScript primitive/union types to JSON Schema types."""
    ts_type_str = ts_type_str.strip()

    if ts_type_str.endswith("[]"):
        item_type = ts_type_str[:-2]
        return {"type": "array", "items": parse_ts_type(item_type)}

    if ts_type_str.startswith("Array<") and ts_type_str.endswith(">"):
        item_type = ts_type_str[6:-1]
        return {"type": "array", "items": parse_ts_type(item_type)}

    if ts_type_str.startswith("Record<"):
        return {"type": "object"}

    # Handle nullable / union with null
    if " | null" in ts_type_str or "null | " in ts_type_str:
        non_null_type = ts_type_str.replace(" | null", "").replace("null | ", "").strip()
        base_schema = parse_ts_type(non_null_type)
        return {"anyOf": [base_schema, {"type": "null"}]}

    # Handle string literal union: "a" | "b" | "c"
    if '"' in ts_type_str or "'" in ts_type_str:
        values = [v.strip().strip("\"'") for v in ts_type_str.split("|")]
        return {"type": "string", "enum": values}

    if ts_type_str == "string":
        return {"type": "string"}
    elif ts_type_str == "number":
        return {"type": "number"}
    elif ts_type_str == "boolean":
        return {"type": "boolean"}
    elif ts_type_str in ("any", "unknown", "object"):
        return {"type": ["object", "string", "number", "boolean", "array", "null"]}

    return {"$ref": f"#/definitions/{ts_type_str}"}


def extract_schemas_from_file(file_path: Path) -> Dict[str, Any]:
    """Extract all interfaces and type aliases from TypeScript file into JSON Schema definitions."""
    content = file_path.read_text(encoding="utf-8")
    definitions: Dict[str, Any] = {}

    # Extract type aliases (e.g. export type HubType = "ingestion" | "agent" ...;)
    type_alias_pattern = re.compile(r"export\s+type\s+(\w+)\s*=\s*([^;]+);", re.MULTILINE)
    for match in type_alias_pattern.finditer(content):
        name = match.group(1)
        raw_type = match.group(2).strip()
        definitions[name] = parse_ts_type(raw_type)

    # Extract interfaces
    interface_pattern = re.compile(
        r"export\s+interface\s+(\w+)(?:\s+extends\s+([\w\s,]+))?\s*\{([^}]+)\}",
        re.MULTILINE | re.DOTALL,
    )

    for match in interface_pattern.finditer(content):
        name = match.group(1)
        body = match.group(3)
        properties: Dict[str, Any] = {}
        required: List[str] = []
        brace_depth = 0

        for line in body.split("\n"):
            line = line.strip()
            if not line or line.startswith("//") or line.startswith("/*") or line.startswith("*"):
                continue

            open_cnt = line.count("{")
            close_cnt = line.count("}")

            if brace_depth == 0:
                field_match = re.match(r"^(\w+)(\?)?:\s*([^;]+);?", line)
                if field_match:
                    field_name = field_match.group(1)
                    is_optional = bool(field_match.group(2))
                    field_type_raw = field_match.group(3).strip().rstrip(";")

                    if "{" in field_type_raw:
                        properties[field_name] = {"type": "object"}
                    else:
                        properties[field_name] = parse_ts_type(field_type_raw)

                    if not is_optional and not (" | null" in field_type_raw or "null | " in field_type_raw):
                        required.append(field_name)

            brace_depth += (open_cnt - close_cnt)
            if brace_depth < 0:
                brace_depth = 0

        definitions[name] = {
            "type": "object",
            "properties": properties,
            "required": required,
        }

    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "ContAIned API Frontend Types",
        "definitions": definitions,
    }


def main():
    root = Path(__file__).resolve().parent.parent
    ts_file = root / "frontend" / "src" / "types" / "api.ts"
    out_file = root / "frontend_api_schemas.json"

    if not ts_file.exists():
        print(f"File {ts_file} does not exist.")
        return

    schemas = extract_schemas_from_file(ts_file)
    out_file.write_text(json.dumps(schemas, indent=2), encoding="utf-8")
    print(f"Extracted {len(schemas['definitions'])} types/interfaces into {out_file}")


if __name__ == "__main__":
    main()
