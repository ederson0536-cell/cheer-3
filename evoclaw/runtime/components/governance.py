#!/usr/bin/env python3
"""
Governance Gate - Based on SYSTEM_FRAMEWORK_PROPOSAL.md Section 16
Complete proposal governance system
"""

import json
from pathlib import Path

from evoclaw.workspace_resolver import resolve_workspace
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum

WORKSPACE = resolve_workspace(__file__)


class ProposalStatus(Enum):
    """Proposal status"""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"
    ROLLED_BACK = "rolled_back"


class GovernanceLevel(Enum):
    """Governance levels"""
    AUTONOMOUS = "autonomous"     # Auto-apply if keyword match
    ADVISORY = "advisory"        # Auto-apply all
    SUPERVISED = "supervised"    # All require human approval


class GovernanceGate:
    """Complete Governance Gate"""
    
    def __init__(self):
        self.governance_dir = WORKSPACE / "memory" / "governance"
        self.governance_dir.mkdir(parents=True, exist_ok=True)
        
        self.pending_file = self.governance_dir / "pending.jsonl"
        self.approved_file = self.governance_dir / "approved.jsonl"
        self.rejected_file = self.governance_dir / "rejected.jsonl"
        self.canary_file = self.governance_dir / "canary.jsonl"
        self.published_file = self.governance_dir / "published.jsonl"
        
        # Initialize files
        for f in [self.pending_file, self.approved_file, self.rejected_file, 
                  self.canary_file, self.published_file]:
            if not f.exists():
                f.touch()
        
        self.config = self._load_config()
    
    def _load_config(self) -> Dict:
        """Load governance config"""
        
        config_file = WORKSPACE / "evoclaw" / "runtime" / "config" / "governance.json"
        
        if config_file.exists():
            with open(config_file) as f:
                return json.load(f)
        
        # Default config
        default = {
            "governance_level": "advisory",
            "auto_approve_categories": ["scenario_discovery", "knowledge"],
            "auto_approve_min_confidence": 0.8,
            "canary_required_for": ["rule_change", "skill_change"],
            "rollback_on_fail": True
        }
        
        config_file.parent.mkdir(parents=True, exist_ok=True)
        with open(config_file, "w") as f:
            json.dump(default, f, indent=2)
        
        return default
    
    def should_auto_approve(self, proposal: Dict) -> bool:
        """Check if proposal should auto-approve"""
        
        level = self.config.get("governance_level", "advisory")
        
        if level == "autonomous":
            # Auto-approve if keyword match
            category = proposal.get("category", "")
            confidence = proposal.get("confidence", 0)
            
            auto_categories = self.config.get("auto_approve_categories", [])
            
            if category in auto_categories:
                return True
            
            if confidence >= self.config.get("auto_approve_min_confidence", 0.8):
                return True
        
        elif level == "advisory":
            # Auto-approve all
            return True
        
        # Supervised - always require approval
        return False
    
    def submit(self, proposal: Dict) -> str:
        """Submit proposal for governance"""
        
        proposal_id = f"prop_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        entry = {
            "proposal_id": proposal_id,
            **proposal,
            "status": ProposalStatus.PENDING.value,
            "submitted_at": datetime.now().isoformat(),
            "reviewed_at": None,
            "reviewed_by": None,
            "review_notes": None
        }
        
        with open(self.pending_file, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        
        # Check auto-approve
        if self.should_auto_approve(proposal):
            self.approve(proposal_id, "auto", "Auto-approved by governance level")
        
        return proposal_id
    
    def approve(self, proposal_id: str, reviewer: str = "system", notes: str = None) -> bool:
        """Approve a proposal"""
        
        # Move from pending to approved
        return self._move_proposal(
            proposal_id,
            self.pending_file,
            self.approved_file,
            {
                "status": ProposalStatus.APPROVED.value,
                "reviewed_at": datetime.now().isoformat(),
                "reviewed_by": reviewer,
                "review_notes": notes
            }
        )
    
    def reject(self, proposal_id: str, reviewer: str = "system", reason: str = None) -> bool:
        """Reject a proposal"""
        
        return self._move_proposal(
            proposal_id,
            self.pending_file,
            self.rejected_file,
            {
                "status": ProposalStatus.REJECTED.value,
                "reviewed_at": datetime.now().isoformat(),
                "reviewed_by": reviewer,
                "review_notes": reason
            }
        )
    
    def start_canary(self, proposal_id: str, scope: str = "test") -> bool:
        """Start canary deployment"""
        
        # Must be approved first
        if not self._is_approved(proposal_id):
            return False
        
        entry = {
            "proposal_id": proposal_id,
            "scope": scope,
            "started_at": datetime.now().isoformat(),
            "status": "running",
            "metrics": {},
            "results": {}
        }
        
        with open(self.canary_file, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        
        return True
    
    def complete_canary(self, proposal_id: str, success: bool, metrics: Dict = None) -> bool:
        """Complete canary deployment"""
        
        entries = []
        
        if self.canary_file.exists():
            with open(self.canary_file) as f:
                for line in f:
                    entry = json.loads(line)
                    if entry["proposal_id"] == proposal_id:
                        entry["status"] = "success" if success else "failed"
                        entry["completed_at"] = datetime.now().isoformat()
                        entry["metrics"] = metrics or {}
                        
                        # If successful, publish
                        if success:
                            self.publish(proposal_id)
                    
                    entries.append(entry)
        
        with open(self.canary_file, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        
        return success
    
    def publish(self, proposal_id: str) -> bool:
        """Publish approved proposal"""
        
        # Move from approved to published
        return self._move_proposal(
            proposal_id,
            self.approved_file,
            self.published_file,
            {
                "status": ProposalStatus.PUBLISHED.value,
                "published_at": datetime.now().isoformat()
            }
        )
    
    def rollback(self, proposal_id: str, reason: str) -> bool:
        """Rollback published proposal"""
        
        # Move from published to rolled_back
        return self._move_proposal(
            proposal_id,
            self.published_file,
            self.rejected_file,
            {
                "status": ProposalStatus.ROLLED_BACK.value,
                "rolled_back_at": datetime.now().isoformat(),
                "rollback_reason": reason
            }
        )
    
    def _move_proposal(self, proposal_id: str, from_file: Path, to_file: Path, updates: Dict) -> bool:
        """Move proposal between files with updates"""
        
        if not from_file.exists():
            return False
        
        entries = []
        moved = False
        
        with open(from_file) as f:
            for line in f:
                entry = json.loads(line)
                if entry.get("proposal_id") == proposal_id:
                    entry.update(updates)
                    moved = True
                entries.append(entry)
        
        if moved:
            # Rewrite source
            with open(from_file, "w") as f:
                for entry in entries:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            
            # Add to destination
            with open(to_file, "a") as f:
                for entry in entries:
                    if entry.get("proposal_id") == proposal_id:
                        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        
        return moved
    
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
                except:
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
        """Read proposals from file"""
        
        if not file_path.exists():
            return []
        
        results = []
        with open(file_path) as f:
            for line in f:
                try:
                    results.append(json.loads(line))
                except:
                    continue
        
        return results
    
    def get_stats(self) -> Dict:
        """Get governance stats"""
        
        return {
            "pending": len(self.get_pending()),
            "approved": len(self.get_approved()),
            "published": len(self.get_published()),
            "governance_level": self.config.get("governance_level", "advisory")
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
    
    # Test auto-approve
    test_proposal = {
        "category": "scenario_discovery",
        "confidence": 0.85,
        "description": "Test proposal"
    }
    
    print(f"\nShould auto-approve: {gate.should_auto_approve(test_proposal)}")
