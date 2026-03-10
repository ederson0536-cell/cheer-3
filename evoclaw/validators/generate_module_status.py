#!/usr/bin/env python3
"""Generate import status report for modules under evoclaw/runtime."""

from __future__ import annotations

import importlib
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any

WORKSPACE = Path(__file__).parent.parent.parent
sys.path.insert(0, str(WORKSPACE))


def find_runtime_modules(runtime_dir: Path, repo_root: Path) -> list[tuple[str, str]]:
    """Return list of (module_name, relative_file_path)."""
    modules: list[tuple[str, str]] = []
    for py_file in sorted(runtime_dir.rglob("*.py")):
        if "__pycache__" in py_file.parts:
            continue

        relative_path = py_file.relative_to(repo_root)
        module_name = ".".join(relative_path.with_suffix("").parts)
        modules.append((module_name, str(relative_path)))
    return modules


def check_import(module_name: str) -> dict[str, Any]:
    """Try importing a module and return status payload."""
    try:
        importlib.import_module(module_name)
        return {"can_import": True, "status": "ok"}
    except Exception as exc:  # noqa: BLE001
        return {"can_import": False, "status": "error", "error": f"{type(exc).__name__}: {exc}"}


def main() -> int:
    script_path = Path(__file__).resolve()
    repo_root = script_path.parents[2]
    runtime_dir = repo_root / "evoclaw" / "runtime"
    docs_dir = repo_root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)

    module_rows: list[dict[str, Any]] = []
    for module_name, file_path in find_runtime_modules(runtime_dir, repo_root):
        result = check_import(module_name)
        module_rows.append(
            {
                "module_name": module_name,
                "file_path": file_path,
                "can_import": result["can_import"],
                "status": result["status"],
                **({"error": result["error"]} if "error" in result else {}),
            }
        )

    today = date.today().isoformat()
    output_path = docs_dir / f"module-status-{today}.json"
    payload = {
        "generated_at": f"{today}",
        "runtime_dir": str(runtime_dir.relative_to(repo_root)),
        "total_modules": len(module_rows),
        "importable_modules": sum(1 for row in module_rows if row["can_import"]),
        "failed_modules": sum(1 for row in module_rows if not row["can_import"]),
        "modules": module_rows,
    }

    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Saved: {output_path}")
    for row in module_rows:
        mark = "OK" if row["can_import"] else "FAIL"
        print(f"{mark:<4} {row['module_name']} [{row['status']}]")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
