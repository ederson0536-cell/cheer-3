#!/usr/bin/env python3
"""
EvoClaw Main Entry Point

Routes incoming messages through the configured message processing flow
(`runtime/message_handler.py`) so hooks, runtime state, and memory logging are
all applied consistently.
"""

import json
import sys
from pathlib import Path

# Ensure imports work whether running from workspace root
# (`python evoclaw/run.py`) or from inside `evoclaw`.
WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_ROOT = WORKSPACE_ROOT / "evoclaw" / "runtime"
for p in (WORKSPACE_ROOT, RUNTIME_ROOT):
    p_str = str(p)
    if p_str not in sys.path:
        sys.path.insert(0, p_str)

from evoclaw.runtime.ingress_router import route_message
from evoclaw.runtime.interfaces.passive_learning import get_passive_learner
from evoclaw.runtime.interfaces.governance import get_governance_gate
from evoclaw.runtime.components.active_learning import get_active_learner


def run(message: str, context: dict | None = None) -> dict:
    """Process one message through the centralized ingress router."""
    payload = route_message(
        message,
        source="run.py",
        channel="cli",
        metadata={"context": context or {}},
    )
    payload["context"] = context or {}
    return payload


def heartbeat():
    """Run heartbeat cycle."""
    print("\n💓 EvoClaw Heartbeat")

    print("\n[Passive Learning]")
    learner = get_passive_learner()
    result = learner.run_cycle()
    print(f"    Analyzed: {result['stats']['total_tasks']} tasks")
    print(f"    Success rate: {result['stats']['success_rate']:.0%}")

    print("\n[Active Learning]")
    active = get_active_learner()
    al_result = active.run_cycle()
    print(f"    Validated: {len(al_result['validation']['validated'])} candidates")

    print("\n[Governance]")
    gate = get_governance_gate()
    stats = gate.get_stats()
    print(f"    Pending: {stats['pending']}, Published: {stats['published']}")

    print("\n💓 Heartbeat complete")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "heartbeat":
            heartbeat()
        else:
            payload = run(" ".join(sys.argv[1:]))
            print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        payload = run("测试运行")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
