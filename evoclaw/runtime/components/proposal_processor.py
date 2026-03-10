#!/usr/bin/env python3
"""
Complete Proposal Processor - Week4 enhancement
- priority queue
- similarity merge / dedup
- observable merge stats
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
        self.stats_file = PROPOSALS_DIR / "processor_stats.json"

        for f in [self.pending_file, self.published_file]:
            if not f.exists():
                f.touch()

        if not self.stats_file.exists():
            self._save_stats({"added": 0, "merged": 0, "updated_at": None})

    def _load_stats(self) -> Dict:
        try:
            with open(self.stats_file) as f:
                return json.load(f)
        except Exception:
            return {"added": 0, "merged": 0, "updated_at": None}

    def _save_stats(self, stats: Dict):
        stats["updated_at"] = datetime.now().isoformat()
        with open(self.stats_file, "w") as f:
            json.dump(stats, f, indent=2, ensure_ascii=False)

    def _normalize_text(self, value: str) -> str:
        return " ".join((value or "").lower().split())

    def _fingerprint(self, proposal: Dict) -> str:
        category = self._normalize_text(str(proposal.get("category", "")))
        title = self._normalize_text(str(proposal.get("title", "")))
        description = self._normalize_text(str(proposal.get("description", "")))
        source_hook = self._normalize_text(str(proposal.get("source_hook", "")))
        return f"{category}|{title[:80]}|{description[:160]}|{source_hook}"

    def _compute_priority(self, proposal: Dict) -> int:
        risk_map = {"critical": 100, "high": 80, "medium": 50, "low": 20}
        base = int(float(proposal.get("confidence", 0) or 0) * 100)
        task_risk = str(proposal.get("task_risk_level", "low")).lower()
        category = str(proposal.get("category", "")).lower()
        bonus = 20 if category in {"repeated_failure", "governance"} else 0
        return base + risk_map.get(task_risk, 20) + bonus

    def add(self, proposal: Dict) -> str:
        """Add new proposal with dedup+similarity merge and priority assignment."""

        proposal_id = f"prop_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"
        fingerprint = self._fingerprint(proposal)
        pending = self._read_pending()

        # similarity merge (exact fingerprint in v1)
        for existing in pending:
            if existing.get("similarity_fingerprint") != fingerprint:
                continue
            existing["merge_count"] = int(existing.get("merge_count", 1)) + 1
            existing["updated_at"] = datetime.now().isoformat()
            if proposal.get("description"):
                existing.setdefault("merged_descriptions", [])
                existing["merged_descriptions"].append(proposal["description"])
            existing["confidence"] = max(
                float(existing.get("confidence", 0) or 0),
                float(proposal.get("confidence", 0) or 0),
            )
            existing["priority_score"] = self._compute_priority(existing)
            self._rewrite_pending(pending)

            stats = self._load_stats()
            stats["merged"] = int(stats.get("merged", 0)) + 1
            self._save_stats(stats)
            return existing["proposal_id"]

        entry = {
            "proposal_id": proposal_id,
            **proposal,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "votes": 0,
            "rejected_count": 0,
            "merge_count": 1,
            "similarity_fingerprint": fingerprint,
            "priority_score": self._compute_priority(proposal),
        }

        with open(self.pending_file, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        stats = self._load_stats()
        stats["added"] = int(stats.get("added", 0)) + 1
        self._save_stats(stats)

        return proposal_id

    def add_proposal(self, proposal_type: str, category: str, description: str, task_id: str, confidence: float = 0.5, **kwargs) -> str:
        """Compatibility wrapper for runtime callsites."""
        payload = {
            "type": proposal_type,
            "category": category,
            "description": description,
            "task_id": task_id,
            "confidence": confidence,
            **kwargs,
        }
        return self.add(payload)

    def get_priority_queue(self, limit: int = 20) -> List[Dict]:
        proposals = self._read_pending()
        proposals.sort(
            key=lambda p: (
                -int(p.get("priority_score", 0)),
                p.get("created_at", ""),
            )
        )
        return proposals[:limit]

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
                "avg_merge_count": sum(int(p.get("merge_count", 1)) for p in props) / len(props),
                "suggestion": self._generate_suggestion(category)
            })

        return {
            "total": len(proposals),
            "clusters": cluster_list,
            "priority_queue_top5": [p["proposal_id"] for p in self.get_priority_queue(5)],
            "stats": self._load_stats(),
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
            self._rewrite_pending(entries)
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
            self._rewrite_pending(entries)

        return moved

    def _rewrite_pending(self, entries: List[Dict]):
        with open(self.pending_file, "w") as f:
            for e in entries:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")

    def _read_pending(self) -> List[Dict]:
        """Read pending proposals"""

        proposals = []

        if self.pending_file.exists():
            with open(self.pending_file) as f:
                for line in f:
                    try:
                        proposals.append(json.loads(line))
                    except Exception:
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
