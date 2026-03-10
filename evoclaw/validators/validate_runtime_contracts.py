#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "runtime" / "contracts"
EXAMPLES = ROOT / "runtime" / "examples"

PAIRS = [
    (CONTRACTS / "task_subtask.schema.json", EXAMPLES / "task_subtask.example.json"),
    (CONTRACTS / "skill_registry.schema.json", EXAMPLES / "skill_registry.example.json"),
    (CONTRACTS / "proposal_pipeline.schema.json", EXAMPLES / "proposal_pipeline.example.json"),
    (CONTRACTS / "decision_trace.schema.json", EXAMPLES / "decision_trace.example.json"),
]


def main() -> int:
    try:
        import jsonschema  # type: ignore
    except Exception:
        print("jsonschema not installed; basic JSON parse checks only", file=sys.stderr)
        for _, example in PAIRS:
            json.loads(example.read_text(encoding="utf-8"))
        return 0

    ok = True
    for schema_path, example_path in PAIRS:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        payload = json.loads(example_path.read_text(encoding="utf-8"))
        try:
            jsonschema.validate(payload, schema)
            print(f"OK: {example_path.name} matches {schema_path.name}")
        except Exception as e:
            ok = False
            print(f"FAIL: {example_path.name} -> {e}", file=sys.stderr)

    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
