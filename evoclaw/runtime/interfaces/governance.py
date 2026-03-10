#!/usr/bin/env python3
"""Governance interface boundary."""

from typing import Any, Dict, List, Optional, Protocol, runtime_checkable


@runtime_checkable
class GovernanceGate(Protocol):
    """Behavior contract exposed to runtime/business layers."""

    def should_auto_approve(self, proposal: Dict[str, Any]) -> bool:
        ...

    def submit(self, proposal: Dict[str, Any]) -> str:
        ...

    def approve(self, proposal_id: str, reviewer: str = "system", notes: str = None) -> bool:
        ...

    def reject(self, proposal_id: str, reviewer: str = "system", reason: str = None) -> bool:
        ...

    def start_canary(self, proposal_id: str, scope: str = "test") -> bool:
        ...

    def complete_canary(
        self, proposal_id: str, success: bool, metrics: Optional[Dict[str, Any]] = None
    ) -> bool:
        ...

    def publish(self, proposal_id: str) -> bool:
        ...

    def rollback(self, proposal_id: str, reason: str) -> bool:
        ...

    def get_pending(self) -> List[Dict[str, Any]]:
        ...

    def get_approved(self) -> List[Dict[str, Any]]:
        ...

    def get_published(self) -> List[Dict[str, Any]]:
        ...

    def get_stats(self) -> Dict[str, Any]:
        ...


def get_governance_gate() -> GovernanceGate:
    """Interface-level factory. Business code should import from here."""
    from components.governance import get_governance_gate as _get_governance_gate

    return _get_governance_gate()
