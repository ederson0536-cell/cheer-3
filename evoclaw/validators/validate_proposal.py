#!/usr/bin/env python3
"""
EvoClaw Proposal Validator (SQLite-first).

Usage:
  python3 evoclaw/validators/validate_proposal.py <db_or_jsonl> <soul_md_path> [--status pending]
"""

import json
import os
import re
import sqlite3
import sys

MUTABLE_TAG = "[MUTABLE]"
CORE_TAG = "[CORE]"
VALID_CHANGE_TYPES = {"add", "modify", "remove"}
PROP_ID_PATTERN = re.compile(r"^(PROP-|prop-)")


def _is_db_path(path):
    return str(path).endswith(".db")


def load_soul(soul_path):
    if not os.path.exists(soul_path):
        return None, None, None
    with open(soul_path, "r", encoding="utf-8") as f:
        content = f.read()
    lines = content.split("\n")
    sections = set()
    subsections = {}
    current_section = None
    for line in lines:
        if line.startswith("## ") and not line.startswith("### "):
            current_section = line.strip()
            sections.add(current_section)
            subsections[current_section] = set()
        elif line.startswith("### ") and current_section:
            subsections[current_section].add(line.strip())
    bullet_lines = {line.strip() for line in lines if line.strip().startswith("- ")}
    return sections, subsections, bullet_lines


def _load_proposals_db(db_path, status=None):
    out = []
    with sqlite3.connect(db_path) as conn:
        conn.row_factory = sqlite3.Row
        sql = "SELECT * FROM proposals"
        params = []
        if status:
            sql += " WHERE status = ?"
            params.append(status)
        sql += " ORDER BY created_at DESC LIMIT 5000"
        for row in conn.execute(sql, params).fetchall():
            proposal = {}
            metadata_raw = row["metadata_json"]
            if metadata_raw:
                try:
                    parsed = json.loads(metadata_raw)
                    if isinstance(parsed, dict):
                        proposal = dict(parsed)
                except Exception:
                    pass
            proposal.setdefault("id", row["id"])
            proposal.setdefault("type", row["type"])
            proposal.setdefault("content", row["content"])
            proposal.setdefault("status", row["status"])
            proposal.setdefault("source", row["source"])
            proposal.setdefault("created_at", row["created_at"])
            proposal.setdefault("updated_at", row["updated_at"])
            out.append(proposal)
    return out


def _load_proposals_jsonl(path):
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                parsed = json.loads(line)
                if isinstance(parsed, dict):
                    out.append(parsed)
            except json.JSONDecodeError:
                continue
    return out


def _validate_structured(prop, sections, subsections, bullet_lines):
    errors = []
    change_type = prop.get("change_type", "")
    if change_type not in VALID_CHANGE_TYPES:
        errors.append({"field": "change_type", "message": f"Invalid change_type: {change_type}"})
        return errors

    tag = prop.get("tag", "")
    if tag == CORE_TAG:
        errors.append({"field": "tag", "message": "Proposal attempts to modify [CORE]"})
    if tag and tag not in {MUTABLE_TAG, CORE_TAG}:
        errors.append({"field": "tag", "message": f"Invalid tag: {tag}"})

    current = str(prop.get("current_content") or "").strip()
    proposed = str(prop.get("proposed_content") or "").strip()
    if change_type in {"modify", "remove"} and not current:
        errors.append({"field": "current_content", "message": f"current_content is required for {change_type}"})
    if change_type in {"modify", "remove"} and current and current not in bullet_lines:
        errors.append({"field": "current_content", "message": "current_content not found in SOUL.md"})
    if change_type in {"add", "modify"}:
        if not proposed.startswith("- "):
            errors.append({"field": "proposed_content", "message": "proposed_content must start with '- '"})
        if not proposed.endswith(MUTABLE_TAG):
            errors.append({"field": "proposed_content", "message": "proposed_content must end with [MUTABLE]"})

    target_section = prop.get("target_section", "")
    target_sub = prop.get("target_subsection", "")
    if target_section and target_section not in sections:
        errors.append({"field": "target_section", "message": f"Section not found: {target_section}"})
    if target_section and target_sub and target_sub not in subsections.get(target_section, set()):
        errors.append({"field": "target_subsection", "message": f"Subsection not found: {target_sub}"})
    return errors


def validate(proposals_input, soul_path, status=None):
    errors = []
    warnings = []
    seen_ids = set()

    sections, subsections, bullet_lines = load_soul(soul_path)
    if sections is None:
        return {"status": "FAIL", "file": proposals_input, "errors": [{"field": None, "message": f"SOUL.md not found: {soul_path}"}], "warnings": []}

    if not os.path.exists(proposals_input):
        return {"status": "PASS", "file": proposals_input, "errors": [], "warnings": [{"message": "Proposal input not found; treated as empty"}]}

    proposals = _load_proposals_db(proposals_input, status=status) if _is_db_path(proposals_input) else _load_proposals_jsonl(proposals_input)
    for prop in proposals:
        pid = str(prop.get("id") or "")
        if not pid:
            errors.append({"field": "id", "message": "Missing proposal id"})
            continue
        if not PROP_ID_PATTERN.match(pid):
            warnings.append({"field": "id", "message": f"Unexpected proposal id format: {pid}"})
        if pid in seen_ids:
            errors.append({"field": "id", "message": f"Duplicate proposal id: {pid}"})
        seen_ids.add(pid)

        content = prop.get("content", "")
        if not isinstance(content, str) or not content.strip():
            errors.append({"field": "content", "message": "content is empty"})

        is_structured = any(k in prop for k in ("change_type", "current_content", "proposed_content"))
        if is_structured:
            errors.extend(_validate_structured(prop, sections, subsections, bullet_lines))

    return {"status": "FAIL" if errors else "PASS", "file": proposals_input, "errors": errors, "warnings": warnings, "stats": {"validated": len(proposals)}}


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: validate_proposal.py <db_or_jsonl> <soul_md_path> [--status pending]", file=sys.stderr)
        sys.exit(2)
    proposals_input = sys.argv[1]
    soul_path = sys.argv[2]
    status = None
    if "--status" in sys.argv:
        idx = sys.argv.index("--status")
        if idx + 1 < len(sys.argv):
            status = sys.argv[idx + 1]
    result = validate(proposals_input, soul_path, status=status)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    sys.exit(0 if result["status"] == "PASS" else 1)
