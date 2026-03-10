#!/usr/bin/env python3
"""Passive learning interface boundary."""

from typing import Any, Dict, List, Protocol, runtime_checkable


@runtime_checkable
class PassiveLearner(Protocol):
    """Behavior contract exposed to runtime/business layers."""

    def analyze(self, days: int = 7) -> Dict[str, Any]:
        ...

    def identify_improvements(self, days: int = 7) -> List[Dict[str, Any]]:
        ...

    def generate_proposals(self) -> int:
        ...

    def run_cycle(self) -> Dict[str, Any]:
        ...

    def analyze_rule_effectiveness(self) -> List[Dict[str, Any]]:
        ...


def get_passive_learner() -> PassiveLearner:
    """Interface-level factory. Business code should import from here."""
    from components.passive_learning import get_passive_learner as _get_passive_learner

    return _get_passive_learner()
