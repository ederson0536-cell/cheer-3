#!/usr/bin/env python3
"""
Smoke Import Test - Minimal import health check for EvoClaw Runtime
Usage: python3 evoclaw/validators/smoke_import_test.py
Exit code: 0 = all PASS, 1 = any FAIL
"""

import importlib
import sys
from pathlib import Path

WORKSPACE = Path(__file__).parent.parent.parent
RUNTIME_DIR = WORKSPACE / "evoclaw" / "runtime"

# Add workspace to path for imports
sys.path.insert(0, str(WORKSPACE))


def main():
    # Find all Python modules in runtime/
    mods = []
    for p in sorted(RUNTIME_DIR.rglob("*.py")):
        if "__pycache__" in p.parts or p.name.endswith(".bak"):
            continue
        mod = p.with_suffix("").relative_to(WORKSPACE).as_posix().replace("/", ".")
        mods.append(mod)

    ok = 0
    fail = 0
    failed = []

    for m in mods:
        try:
            importlib.import_module(m)
            ok += 1
        except Exception as e:
            fail += 1
            failed.append((m, str(e)[:80]))

    print("=== EvoClaw Runtime Smoke Import Test ===")
    print(f"Total: {len(mods)} | OK: {ok} | FAIL: {fail}")

    if failed:
        print("\nFailed modules:")
        for m, e in failed:
            print(f"  - {m}")
            print(f"    Error: {e}")
        print("\n❌ Import health check FAILED")
        sys.exit(1)
    else:
        print("\n✓ All modules importable")
        print("✓ Import health check PASSED")
        sys.exit(0)


if __name__ == "__main__":
    main()
