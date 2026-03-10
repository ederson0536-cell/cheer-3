#!/usr/bin/env python3
"""
Complete Proposal Processor - Based on SYSTEM_FRAMEWORK_PROPOSAL.md Section 15
Complete proposal lifecycle management
"""

import json
from pathlib import Path

from evoclaw.workspace_resolver import resolve_workspace
from datetime import datetime
from typing import Dict, List
from collections import defaultdict

WORKSPACE = resolve_workspace(__file__)
PROPOSALS_DIR = WORKSPACE / "memory" / "proposals"


class CompleteProposalProcessor:
    """Complete Proposal Processor"""
    
    def __init__(self):
        PROPOSALS_DIR.mkdir(parents=True, exist_ok=True)
        
        self.pending_file = PROPOSALS_DIR / "pending.jsonl"
        self.published_file = PROPOSALS_DIR / "published.jsonl"
        
        for f in [self.pending_file, self.published_file]:
            if not f.exists():
                f.touch()
    
    def add(self, proposal: Dict) -> str:
        """Add new proposal"""
        
        proposal_id = f"prop_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        entry = {
            "proposal_id": proposal_id,
            **proposal,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "votes": 0,
            "rejected_count": 0
        }
        
        with open(self.pending_file, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        
        return proposal_id
    
    def analyze(self) -> Dict:
        """Analyze pending proposals"""
        
        proposals = self._read_pending()
        
        # Cluster by category
        clusters = defaultdict(list)
        for p in proposals:
            clusters[p.get("category", "unknown")].append(p)
        
        cluster_list = []
        for category, props in clusters.items():
            cluster_list.append({
                "category": category,
                "count": len(props),
                "proposals": [p["proposal_id"] for p in props],
                "avg_confidence": sum(p.get("confidence", 0) for p in props) / len(props),
                "suggestion": self._generate_suggestion(category)
            })
        
        return {
            "total": len(proposals),
            "clusters": cluster_list
        }
    
    def _generate_suggestion(self, category: str) -> str:
        """Generate suggestion for category"""
        
        suggestions = {
            "low_success_rate": "Review task requirements and approach",
            "repeated_failure": "Analyze root cause and add validation",
            "high_risk_low_success": "Add confirmation step before execution",
            "performance_degradation": "Review recent changes",
            "scenario_discovery": "Document new pattern for future reference"
        }
        
        return suggestions.get(category, "Review and determine action")
    
    def approve(self, proposal_id: str) -> bool:
        """Approve proposal"""
        return self._move(proposal_id, "approved")
    
    def reject(self, proposal_id: str) -> bool:
        """Reject proposal"""
        return self._move(proposal_id, "rejected")
    
    def publish(self, proposal_id: str) -> bool:
        """Publish approved proposal"""
        
        # Move to published
        entries = []
        moved = False
        
        with open(self.pending_file) as f:
            for line in f:
                entry = json.loads(line)
                if entry["proposal_id"] == proposal_id:
                    if entry["status"] == "approved":
                        entry["status"] = "published"
                        entry["published_at"] = datetime.now().isoformat()
                        moved = True
                entries.append(entry)
        
        if moved:
            with open(self.pending_file, "w") as f:
                for e in entries:
                    f.write(json.dumps(e, ensure_ascii=False) + "\n")
            
            with open(self.published_file, "a") as f:
                for e in entries:
                    if e["proposal_id"] == proposal_id:
                        f.write(json.dumps(e, ensure_ascii=False) + "\n")
        
        return moved
    
    def _move(self, proposal_id: str, status: str) -> bool:
        """Move proposal status"""
        
        entries = []
        moved = False
        
        with open(self.pending_file) as f:
            for line in f:
                entry = json.loads(line)
                if entry["proposal_id"] == proposal_id:
                    entry["status"] = status
                    entry["updated_at"] = datetime.now().isoformat()
                    moved = True
                entries.append(entry)
        
        if moved:
            with open(self.pending_file, "w") as f:
                for e in entries:
                    f.write(json.dumps(e, ensure_ascii=False) + "\n")
        
        return moved
    
    def _read_pending(self) -> List[Dict]:
        """Read pending proposals"""
        
        proposals = []
        
        if self.pending_file.exists():
            with open(self.pending_file) as f:
                for line in f:
                    try:
                        proposals.append(json.loads(line))
                    except:
                        continue
        
        return proposals
    
    def get_pending_count(self) -> int:
        """Get pending count"""
        return len(self._read_pending())


# Global
_processor = None

def get_processor():
    global _processor
    if _processor is None:
        _processor = CompleteProposalProcessor()
    return _processor


if __name__ == "__main__":
    proc = get_processor()
    result = proc.analyze()
    print(f"Pending: {result['total']}, Clusters: {len(result['clusters'])}")
