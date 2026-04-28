#!/usr/bin/env python3
"""
Validate LibreChat Action registry consistency.

Purpose:
- `config-templates/actions/registry.json` is the only wiring source.
- Every OpenAPI JSON spec must be represented in registry.
- Every `wire=true` spec must have agent patterns and valid operationIds.
- Every `wire=false` spec must explain why it is optional/legacy.
"""
from __future__ import annotations

import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).parent.parent
ACTIONS_DIR = ROOT / "config-templates" / "actions"
REGISTRY = ACTIONS_DIR / "registry.json"


def main() -> int:
    errors: list[str] = []
    registry = json.loads(REGISTRY.read_text())
    items = registry.get("actions") or []
    by_file = {item.get("file"): item for item in items}

    spec_files = sorted(p.name for p in ACTIONS_DIR.glob("*.json") if p.name != "registry.json")
    for name in spec_files:
        if name not in by_file:
            errors.append(f"{name}: missing from registry")
    for name in by_file:
        if name not in spec_files:
            errors.append(f"{name}: registry entry has no matching file")

    for item in items:
        name = item.get("file")
        if not name or name not in spec_files:
            continue
        spec = json.loads((ACTIONS_DIR / name).read_text())
        if spec.get("openapi") not in {"3.0.0", "3.0.1", "3.0.2", "3.0.3", "3.1.0"}:
            errors.append(f"{name}: unsupported/missing openapi")
        if not spec.get("info", {}).get("title"):
            errors.append(f"{name}: missing info.title")
        if not spec.get("servers"):
            errors.append(f"{name}: missing servers")

        op_ids = _operation_ids(spec)
        if not op_ids:
            errors.append(f"{name}: no operationId found")
        duplicates = sorted({op for op in op_ids if op_ids.count(op) > 1})
        if duplicates:
            errors.append(f"{name}: duplicated operationId {duplicates}")

        if item.get("wire"):
            if item.get("status") not in {"canonical", "optional"}:
                errors.append(f"{name}: wire=true must be canonical/optional")
            if not item.get("agent_patterns"):
                errors.append(f"{name}: wire=true missing agent_patterns")
        elif not (item.get("reason") or item.get("superseded_by")):
            errors.append(f"{name}: wire=false missing reason/superseded_by")

    if errors:
        print("Action registry validation failed:")
        for e in errors:
            print(f"- {e}")
        return 1
    print(f"✓ action registry ok · {len(spec_files)} specs · {sum(1 for i in items if i.get('wire'))} wired")
    return 0


def _operation_ids(spec: dict) -> list[str]:
    op_ids: list[str] = []
    for methods in (spec.get("paths") or {}).values():
        for method, op in methods.items():
            if method.lower() in {"get", "post", "put", "patch", "delete"}:
                op_id = op.get("operationId")
                if op_id:
                    op_ids.append(op_id)
    return op_ids


if __name__ == "__main__":
    sys.exit(main())
