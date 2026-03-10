#!/usr/bin/env python3
"""
Validate memory.db ownership contract coverage.

Checks:
- ownership contract json exists and is parseable
- every canonical sqlite table has ownership definition
- each table definition includes owner/purpose/field_sources
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from evoclaw.sqlite_memory import SQLiteMemoryStore
CONTRACT_PATH = ROOT / "evoclaw" / "runtime" / "contracts" / "memory_db_ownership.json"

# Canonical runtime tables (exclude views, sqlite internals, and fts backing tables)
CANONICAL_TABLES = {
    "memories",
    "proposals",
    "reflections",
    "graph_entities",
    "graph_relations",
    "soul_history",
    "rules",
    "candidates",
    "system_state",
    "system_logs",
}


def _build_schema_tables() -> set[str]:
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "memory.db"
        store = SQLiteMemoryStore(db_path)
        store.init_schema()
        with store._connect() as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        return {str(r["name"]) for r in rows}


def validate() -> dict[str, object]:
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    if not CONTRACT_PATH.exists():
        return {
            "status": "FAIL",
            "errors": [{"message": f"contract file missing: {CONTRACT_PATH}"}],
            "warnings": [],
        }

    try:
        contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return {
            "status": "FAIL",
            "errors": [{"message": f"invalid json contract: {exc}"}],
            "warnings": [],
        }

    tables = contract.get("tables") if isinstance(contract, dict) else None
    if not isinstance(tables, dict):
        return {
            "status": "FAIL",
            "errors": [{"message": "contract.tables must be an object"}],
            "warnings": [],
        }

    schema_tables = _build_schema_tables()
    missing_in_contract = sorted(CANONICAL_TABLES - set(tables.keys()))
    if missing_in_contract:
        errors.append(
            {
                "message": (
                    "missing table ownership definitions: "
                    + ", ".join(missing_in_contract)
                )
            }
        )

    uncovered_schema_tables = sorted(
        (schema_tables & CANONICAL_TABLES) - set(tables.keys())
    )
    if uncovered_schema_tables:
        errors.append(
            {
                "message": (
                    "contract does not cover canonical schema tables: "
                    + ", ".join(uncovered_schema_tables)
                )
            }
        )

    extra_contract_tables = sorted(set(tables.keys()) - CANONICAL_TABLES)
    if extra_contract_tables:
        warnings.append(
            {
                "message": (
                    "contract includes non-canonical tables (verify intent): "
                    + ", ".join(extra_contract_tables)
                )
            }
        )

    for table_name in sorted(CANONICAL_TABLES & set(tables.keys())):
        spec = tables.get(table_name)
        if not isinstance(spec, dict):
            errors.append({"message": f"{table_name}: definition must be an object"})
            continue
        for required_key in ("owner", "purpose", "field_sources"):
            if required_key not in spec:
                errors.append(
                    {
                        "message": f"{table_name}: missing required key '{required_key}'"
                    }
                )
        if "field_sources" in spec and not isinstance(spec.get("field_sources"), dict):
            errors.append({"message": f"{table_name}: field_sources must be an object"})

    status = "FAIL" if errors else "PASS"
    return {
        "status": status,
        "contract": str(CONTRACT_PATH),
        "canonical_tables": sorted(CANONICAL_TABLES),
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate memory db ownership contract")
    parser.parse_args()

    result = validate()
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
