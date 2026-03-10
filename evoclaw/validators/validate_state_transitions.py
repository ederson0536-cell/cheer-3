#!/usr/bin/env python3
from __future__ import annotations

from typing import Dict, Set

TRANSITIONS: Dict[str, Dict[str, Set[str]]] = {
    "task": {
        "new": {"open", "archived"},
        "open": {"in_progress", "blocked", "awaiting_review"},
        "in_progress": {"blocked", "awaiting_review", "completed", "failed"},
        "blocked": {"open", "failed", "archived"},
        "awaiting_review": {"in_progress", "failed", "archived"},
        "completed": {"archived"},
        "failed": {"archived"},
        "archived": set(),
    },
    "proposal": {
        "draft": {"candidate", "rejected"},
        "candidate": {"review_pending", "rejected"},
        "review_pending": {"canary", "rejected", "archived"},
        "canary": {"active", "rolled_back", "rejected"},
        "active": {"rolled_back", "archived"},
        "rejected": {"archived"},
        "rolled_back": {"archived"},
        "archived": set(),
    },
    "memory": {
        "raw": {"episodic", "archived"},
        "episodic": {"candidate", "semantic", "deprecated", "archived"},
        "candidate": {"semantic", "deprecated", "archived"},
        "semantic": {"deprecated", "archived"},
        "deprecated": {"archived"},
        "archived": set(),
    },
    "file": {
        "active": {"candidate_patch", "locked"},
        "candidate_patch": {"review_pending", "rolled_back"},
        "review_pending": {"published", "rolled_back"},
        "published": {"active", "rolled_back"},
        "rolled_back": {"active", "locked"},
        "locked": {"active"},
    },
}


def validate() -> int:
    failures = []
    for obj, table in TRANSITIONS.items():
        for state, allowed in table.items():
            if state != "archived" and len(allowed) == 0:
                failures.append(f"{obj}.{state} has no outgoing transitions")
            for dst in allowed:
                if dst not in table:
                    failures.append(f"{obj}.{state} -> unknown target {dst}")

    if failures:
        print("STATE_TRANSITION_FAIL")
        for f in failures:
            print("-", f)
        return 1

    print("STATE_TRANSITION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(validate())
