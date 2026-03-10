#!/usr/bin/env python3
"""
Governance Gate - Week4 enhancement
- review quorum
- freeze window
- candidate-first review gate
"""

import json
from pathlib import Path

from evoclaw.workspace_resolver import resolve_workspace
from datetime import datetime
from typing import Dict, List
from enum import Enum

WORKSPACE = resolve_workspace(__file__)
GOVERNANCE_DIR = WORKSPACE / "memory" / "governance"


class ProposalStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"
    ROLLED_BACK = "rolled_back"


class GovernanceGate:
    """Governance controller for proposal review/publish/rollback."""

    def __init__(self):
        GOVERNANCE_DIR.mkdir(parents=True, exist_ok=True)

        self.pending_file = GOVERNANCE_DIR / "pending.jsonl"
        self.approved_file = GOVERNANCE_DIR / "approved.jsonl"
        self.rejected_file = GOVERNANCE_DIR / "rejected.jsonl"
        self.published_file = GOVERNANCE_DIR / "published.jsonl"
        self.canary_file = GOVERNANCE_DIR / "canary.jsonl"

        self.config_file = WORKSPACE / "evoclaw" / "runtime" / "config" / "governance.json"
        self.config = self._load_config()

        for f in [
            self.pending_file,
            self.approved_file,
            self.rejected_file,
            self.published_file,
            self.canary_file,
        ]:
            if not f.exists():
                f.touch()

    def _load_config(self) -> Dict:
        config_file = self.config_file
        if config_file.exists():
            with open(config_file) as f:
                cfg = json.load(f)
            cfg.setdefault("review_quorum", 2)
            cfg.setdefault("freeze_windows", ["00:00-00:00"])
            cfg.setdefault("enforce_freeze_window", False)
            return cfg

        default = {
            "governance_level": "advisory",
            "auto_approve_categories": ["scenario_discovery", "knowledge"],
            "auto_approve_min_confidence": 0.8,
            "canary_required_for": ["rule_change", "skill_change"],
            "rollback_on_fail": True,
            "review_quorum": 2,
            "freeze_windows": ["00:00-00:00"],
            "enforce_freeze_window": False,
        }

        config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(config_file, "w") as f:
            json.dump(default, f, indent=2)

        return default

    def _parse_hhmm(self, value: str) -> int:
        hh, mm = value.split(":")
        return int(hh) * 60 + int(mm)

    def _in_freeze_window(self, now: datetime | None = None) -> bool:
        if not self.config.get("enforce_freeze_window", False):
            return False
        windows = self.config.get("freeze_windows", [])
        if not windows:
            return False

        now = now or datetime.now()
        minute = now.hour * 60 + now.minute

        for window in windows:
            try:
                start_s, end_s = str(window).split("-")
                start = self._parse_hhmm(start_s)
                end = self._parse_hhmm(end_s)
            except Exception:
                continue

            if start == end:
                # full-day freeze
                return True
            if start < end and start <= minute < end:
                return True
            if start > end and (minute >= start or minute < end):
                return True

        return False

    def _append(self, file_path: Path, payload: Dict):
        with open(file_path, "a") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _ensure_review_votes(self, entry: Dict):
        if not isinstance(entry.get("review_votes"), list):
            entry["review_votes"] = []

    def should_auto_approve(self, proposal: Dict) -> bool:
        """Check if proposal should auto-approve."""

        level = self.config.get("governance_level", "advisory")

        if self._in_freeze_window():
            return False

        # Week4 guard: candidate objects are review-only.
        if str(proposal.get("proposal_status") or proposal.get("status") or "").lower() in {"candidate", "review_pending"}:
            return False

        if level == "autonomous":
            category = proposal.get("category", "")
            confidence = proposal.get("confidence", 0)

            auto_categories = self.config.get("auto_approve_categories", [])

            if category in auto_categories:
                return True

            if confidence >= self.config.get("auto_approve_min_confidence", 0.8):
                return True

        elif level == "advisory":
            return True

        return False

    def submit(self, proposal: Dict) -> str:
        """Submit proposal for governance."""

        proposal_id = f"prop_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

        entry = {
            "proposal_id": proposal_id,
            **proposal,
            "status": ProposalStatus.PENDING.value,
            "submitted_at": datetime.now().isoformat(),
            "reviewed_at": None,
            "reviewed_by": None,
            "review_notes": None,
            "proposal_status": "review_pending",
            "review_votes": [],
            "required_quorum": int(self.config.get("review_quorum", 2)),
        }

        self._append(self.pending_file, entry)

        if self.should_auto_approve(proposal):
            self.approve(proposal_id, "auto", "Auto-approved by governance level")

        return proposal_id

    def add_review_vote(self, proposal_id: str, reviewer: str, approve: bool, notes: str = "") -> bool:
        entries = self._read_file(self.pending_file)
        changed = False

        for entry in entries:
            if entry.get("proposal_id") != proposal_id:
                continue

            self._ensure_review_votes(entry)
            # upsert same reviewer vote
            entry["review_votes"] = [v for v in entry["review_votes"] if v.get("reviewer") != reviewer]
            entry["review_votes"].append({
                "reviewer": reviewer,
                "approve": bool(approve),
                "notes": notes,
                "voted_at": datetime.now().isoformat(),
            })
            entry["updated_at"] = datetime.now().isoformat()
            changed = True

        if changed:
            self._rewrite_file(self.pending_file, entries)
        return changed

    def can_approve(self, proposal_id: str) -> bool:
        if self._in_freeze_window():
            return False

        quorum = int(self.config.get("review_quorum", 2))
        for entry in self.get_pending():
            if entry.get("proposal_id") != proposal_id:
                continue
            votes = entry.get("review_votes", [])
            approve_count = sum(1 for v in votes if v.get("approve") is True)
            return approve_count >= quorum
        return False

    def approve(self, proposal_id: str, reviewer: str = "system", notes: str = None) -> bool:
        """Approve a proposal if quorum passes."""

        if reviewer != "auto":
            self.add_review_vote(proposal_id, reviewer, True, notes or "")

        if not self.can_approve(proposal_id):
            return False

        return self._move_proposal(
            proposal_id,
            self.pending_file,
            self.approved_file,
            {
                "status": ProposalStatus.APPROVED.value,
                "proposal_status": "canary",
                "reviewed_at": datetime.now().isoformat(),
                "reviewed_by": reviewer,
                "review_notes": notes,
            },
        )

    def reject(self, proposal_id: str, reviewer: str = "system", reason: str = None) -> bool:
        """Reject a proposal."""

        self.add_review_vote(proposal_id, reviewer, False, reason or "")
        return self._move_proposal(
            proposal_id,
            self.pending_file,
            self.rejected_file,
            {
                "status": ProposalStatus.REJECTED.value,
                "proposal_status": "rejected",
                "reviewed_at": datetime.now().isoformat(),
                "reviewed_by": reviewer,
                "review_notes": reason,
            },
        )

    def start_canary(self, proposal_id: str, scope: str = "test") -> bool:
        """Start canary deployment."""

        if not self._is_approved(proposal_id):
            return False

        entry = {
            "proposal_id": proposal_id,
            "scope": scope,
            "started_at": datetime.now().isoformat(),
            "status": "running",
            "metrics": {},
            "results": {},
        }

        self._append(self.canary_file, entry)
        return True

    def complete_canary(self, proposal_id: str, success: bool, metrics: Dict = None) -> bool:
        """Complete canary deployment."""

        entries = []

        if self.canary_file.exists():
            with open(self.canary_file) as f:
                for line in f:
                    entry = json.loads(line)
                    if entry["proposal_id"] == proposal_id:
                        entry["status"] = "success" if success else "failed"
                        entry["completed_at"] = datetime.now().isoformat()
                        entry["metrics"] = metrics or {}

                        if success:
                            self.publish(proposal_id)

                    entries.append(entry)

        self._rewrite_file(self.canary_file, entries)
        return success

    def publish(self, proposal_id: str) -> bool:
        """Publish approved proposal."""

        if self._in_freeze_window():
            return False

        return self._move_proposal(
            proposal_id,
            self.approved_file,
            self.published_file,
            {
                "status": ProposalStatus.PUBLISHED.value,
                "proposal_status": "active",
                "published_at": datetime.now().isoformat(),
            },
        )

    def rollback(self, proposal_id: str, reason: str) -> bool:
        """Rollback published proposal."""

        return self._move_proposal(
            proposal_id,
            self.published_file,
            self.rejected_file,
            {
                "status": ProposalStatus.ROLLED_BACK.value,
                "proposal_status": "rolled_back",
                "rolled_back_at": datetime.now().isoformat(),
                "rollback_reason": reason,
            },
        )

    def _move_proposal(self, proposal_id: str, from_file: Path, to_file: Path, updates: Dict) -> bool:
        """Move proposal between files with updates."""

        if not from_file.exists():
            return False

        entries = []
        moved = False
        moved_entries = []

        with open(from_file) as f:
            for line in f:
                entry = json.loads(line)
                if entry.get("proposal_id") == proposal_id:
                    entry.update(updates)
                    moved = True
                    moved_entries.append(entry)
                    continue
                entries.append(entry)

        if moved:
            self._rewrite_file(from_file, entries)
            with open(to_file, "a") as f:
                for entry in moved_entries:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        return moved

    def _rewrite_file(self, file_path: Path, entries: List[Dict]):
        with open(file_path, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")

    def _is_approved(self, proposal_id: str) -> bool:
        """Check if proposal is approved"""

        if not self.approved_file.exists():
            return False

        with open(self.approved_file) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    if entry.get("proposal_id") == proposal_id:
                        return True
                except Exception:
                    continue

        return False

    def get_pending(self) -> List[Dict]:
        """Get pending proposals"""
        return self._read_file(self.pending_file)

    def get_approved(self) -> List[Dict]:
        """Get approved proposals"""
        return self._read_file(self.approved_file)

    def get_published(self) -> List[Dict]:
        """Get published proposals"""
        return self._read_file(self.published_file)

    def _read_file(self, file_path: Path) -> List[Dict]:
        """Read proposals from file."""

        if not file_path.exists():
            return []

        results = []
        with open(file_path) as f:
            for line in f:
                try:
                    results.append(json.loads(line))
                except Exception:
                    continue

        return results

    def get_stats(self) -> Dict:
        """Get governance stats."""

        pending = self.get_pending()
        review_pending_without_quorum = 0
        quorum = int(self.config.get("review_quorum", 2))
        for p in pending:
            approve_votes = sum(1 for v in p.get("review_votes", []) if v.get("approve") is True)
            if approve_votes < quorum:
                review_pending_without_quorum += 1

        return {
            "pending": len(pending),
            "approved": len(self.get_approved()),
            "published": len(self.get_published()),
            "governance_level": self.config.get("governance_level", "advisory"),
            "review_quorum": quorum,
            "freeze_window_active": self._in_freeze_window(),
            "review_pending_without_quorum": review_pending_without_quorum,
        }


# Global instance
_gate = None

def get_governance_gate() -> GovernanceGate:
    global _gate
    if _gate is None:
        _gate = GovernanceGate()
    return _gate


if __name__ == "__main__":
    gate = GovernanceGate()

    print("=== Governance Stats ===")
    stats = gate.get_stats()
    print(f"Pending: {stats['pending']}")
    print(f"Approved: {stats['approved']}")
    print(f"Published: {stats['published']}")
    print(f"Level: {stats['governance_level']}")

    test_proposal = {
        "category": "scenario_discovery",
        "confidence": 0.85,
        "description": "Test proposal"
    }

    print(f"\nShould auto-approve: {gate.should_auto_approve(test_proposal)}")
