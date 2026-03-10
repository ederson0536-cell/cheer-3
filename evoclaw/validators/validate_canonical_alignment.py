#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

CONTRACTS_DIR = Path(__file__).resolve().parent.parent / 'runtime' / 'contracts'
JSON_SCHEMAS = [
    'task_schema.json',
    'subtask_schema.json',
    'skill_registry_schema.json',
    'decision_trace.schema.json',
    'continuity_resolver.schema.json',
    'task_outcome.schema.json',
    'envelope.schema.json',
]

FORBIDDEN_SYNONYMS = {
    'job_type', 'work_type', 'risk_level', 'risk_profile', 'status', 'ver', 'version_no', 'success_flag', 'result_ok', 'passed'
}

REQUIRED_SUFFIXES = {
    '_id': 'identity field',
    '_status': 'status field',
    '_version': 'version field',
    '_at': 'datetime field',
}


def load_properties(path: Path) -> set[str]:
    data = json.loads(path.read_text(encoding='utf-8'))
    return set(data.get('properties', {}).keys())


def main() -> int:
    violations = []
    all_fields: set[str] = set()

    for rel in JSON_SCHEMAS:
        p = CONTRACTS_DIR / rel
        fields = load_properties(p)
        all_fields |= fields
        bad = sorted(fields & FORBIDDEN_SYNONYMS)
        if bad:
            violations.append(f'{rel}: forbidden fields found {bad}')

    # Minimum canonical presence checks
    must_have = {
        'task_id', 'parent_task_id', 'schema_version', 'policy_version',
        'trace_version', 'router_version', 'trust_level', 'file_scope',
        'message_id', 'session_id', 'continuity_type', 'overall_outcome', 'interaction_success'
    }
    missing = sorted(must_have - all_fields)
    if missing:
        violations.append(f'missing canonical fields across schemas: {missing}')

    if violations:
        print('CANONICAL_ALIGNMENT_FAIL')
        for item in violations:
            print('-', item)
        return 1

    print('CANONICAL_ALIGNMENT_PASS')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
