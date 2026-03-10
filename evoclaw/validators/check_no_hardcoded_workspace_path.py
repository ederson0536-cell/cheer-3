#!/usr/bin/env python3
"""Fail if hardcoded workspace-cheer absolute path remains in code files."""

import json
from pathlib import Path

BLOCKED = "/home/bro/.openclaw/workspace-cheer"
ROOT = Path(__file__).resolve().parents[2]

SKIP_PARTS = {"__pycache__", ".git"}
SKIP_SUFFIX = {".pyc", ".json", ".md", ".txt", ".log"}


def should_check(path: Path) -> bool:
    if any(part in SKIP_PARTS for part in path.parts):
        return False
    if path.suffix in SKIP_SUFFIX and path.name != "evoclaw":
        return False
    # check python and shell-like executable script files only
    if path.suffix in {".py", ".sh"}:
        return True
    if path.name in {"evoclaw"}:  # scripts/evoclaw
        return True
    return False


def main() -> int:
    hits = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or not should_check(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        rel = str(path.relative_to(ROOT))
        if rel == "evoclaw/validators/check_no_hardcoded_workspace_path.py":
            continue
        if BLOCKED in text:
            hits.append(rel)

    if hits:
        print(json.dumps({
            "status": "FAIL",
            "errors": [{"message": f"Hardcoded workspace path found in {len(hits)} file(s)", "files": hits}],
            "warnings": [],
        }, ensure_ascii=False))
        return 1

    print(json.dumps({"status": "PASS", "errors": [], "warnings": []}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
