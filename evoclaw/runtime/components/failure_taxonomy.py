#!/usr/bin/env python3
"""
Failure Taxonomy - Based on SYSTEM_FRAMEWORK_PROPOSAL.md Section 17
Complete failure classification system
"""

import json
from pathlib import Path

from evoclaw.workspace_resolver import resolve_workspace
from typing import Dict, List, Optional
from datetime import datetime

WORKSPACE = resolve_workspace(__file__)


class FailureTaxonomy:
    """Complete failure taxonomy system"""
    
    # Major categories (Section 17.1)
    CATEGORIES = {
        "understanding_error": {
            "severity": "high",
            "description": "Task understanding failed",
            "indicators": ["high_uncertainty", "ambiguous_message", "missing_context"],
            "resolution": "Clarify with user or use memory recall"
        },
        "routing_error": {
            "severity": "high",
            "description": "Skill routing selected wrong skill",
            "indicators": ["low_routing_score", "skill_not_found", "wrong_skill_selected"],
            "resolution": "Update skill registry or routing weights"
        },
        "tool_error": {
            "severity": "medium",
            "description": "Tool execution failed",
            "indicators": ["timeout", "permission_denied", "network_error", "tool_crash"],
            "resolution": "Retry with different approach or report tool issue"
        },
        "memory_miss": {
            "severity": "medium",
            "description": "Memory retrieval failed",
            "indicators": ["empty_recall", "wrong_recall", "memory_not_found"],
            "resolution": "Improve memory indexing or manually add experience"
        },
        "rule_conflict": {
            "severity": "high",
            "description": "Task conflicts with rules",
            "indicators": ["rule_rejected", "permission_denied", "governance_block"],
            "resolution": "Review rules or escalate to governance"
        },
        "execution_timeout": {
            "severity": "medium",
            "description": "Task exceeded time limit",
            "indicators": ["timeout", "slow_execution", "stuck"],
            "resolution": "Break into smaller subtasks or optimize"
        },
        "file_scope_error": {
            "severity": "high",
            "description": "File operation outside scope",
            "indicators": ["path_rejected", "scope_violation", "permission_error"],
            "resolution": "Verify file paths or request scope expansion"
        },
        "hallucinated_assumption": {
            "severity": "critical",
            "description": "Made incorrect assumptions",
            "indicators": ["wrong_fact", "unverified_claim", "assumption_failed"],
            "resolution": "Add verification step to checklist"
        },
        "incomplete_validation": {
            "severity": "medium",
            "description": "Output validation failed",
            "indicators": ["validation_failed", "missing_fields", "wrong_format"],
            "resolution": "Add validation checks or improve output format"
        },
        "dependency_error": {
            "severity": "medium",
            "description": "Subtask dependency failed",
            "indicators": ["dependency_failed", "circular_dependency", "missing_dependency"],
            "resolution": "Reorder dependencies or add fallback"
        },
        "skill_error": {
            "severity": "medium",
            "description": "Skill execution failed",
            "indicators": ["skill_crashed", "wrong_parameters", "api_error"],
            "resolution": "Check skill parameters or use alternative"
        }
    }
    
    def __init__(self):
        self.failures_log = WORKSPACE / "memory" / "failures.jsonl"
        self.failures_log.parent.mkdir(parents=True, exist_ok=True)
        
        if not self.failures_log.exists():
            self.failures_log.touch()
    
    def classify(self, error: str, context: Dict = None) -> Dict:
        """Classify a failure into taxonomy"""
        
        error_lower = error.lower()
        
        # Match to category
        matched_category = None
        matched_indicators = []
        
        for category, info in self.CATEGORIES.items():
            for indicator in info.get("indicators", []):
                if indicator in error_lower:
                    matched_category = category
                    matched_indicators.append(indicator)
                    break
            
            if matched_category:
                break
        
        # If no match, create generic classification
        if not matched_category:
            matched_category = "unknown_error"
            matched_indicators = ["unclassified"]
        
        classification = {
            "category": matched_category,
            "severity": self.CATEGORIES.get(matched_category, {}).get("severity", "medium"),
            "indicators": matched_indicators,
            "resolution": self.CATEGORIES.get(matched_category, {}).get("resolution", "Investigate further"),
            "timestamp": datetime.now().isoformat()
        }
        
        return classification
    
    def log_failure(
        self,
        task_id: str,
        error: str,
        context: Dict = None
    ) -> Dict:
        """Log a failure with classification"""
        
        classification = self.classify(error, context)
        
        entry = {
            "task_id": task_id,
            "error": error,
            "classification": classification,
            "context": context or {},
            "timestamp": datetime.now().isoformat()
        }
        
        with open(self.failures_log, "a") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        
        return entry
    
    def get_failure_stats(self, days: int = 30) -> Dict:
        """Get failure statistics"""
        
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        
        stats = {
            "total_failures": 0,
            "by_category": {},
            "by_severity": {"critical": 0, "high": 0, "medium": 0, "low": 0},
            "recent_failures": []
        }
        
        if not self.failures_log.exists():
            return stats
        
        with open(self.failures_log) as f:
            for line in f:
                try:
                    entry = json.loads(line)
                    
                    if entry.get("timestamp", "") < cutoff:
                        continue
                    
                    stats["total_failures"] += 1
                    
                    cat = entry.get("classification", {}).get("category", "unknown")
                    stats["by_category"][cat] = stats["by_category"].get(cat, 0) + 1
                    
                    sev = entry.get("classification", {}).get("severity", "medium")
                    stats["by_severity"][sev] = stats["by_severity"].get(sev, 0) + 1
                    
                    stats["recent_failures"].append({
                        "task_id": entry.get("task_id"),
                        "category": cat,
                        "severity": sev
                    })
                    
                except:
                    continue
        
        return stats
    
    def get_resolution(self, category: str) -> str:
        """Get resolution for category"""
        
        return self.CATEGORIES.get(category, {}).get("resolution", "Investigate")


# Global instance
_taxonomy = None

def get_failure_taxonomy() -> FailureTaxonomy:
    global _taxonomy
    if _taxonomy is None:
        _taxonomy = FailureTaxonomy()
    return _taxonomy


if __name__ == "__main__":
    taxonomy = FailureTaxonomy()
    
    # Test
    errors = [
        "High uncertainty in task understanding",
        "Network timeout when fetching data",
        "Permission denied for file operation"
    ]
    
    for error in errors:
        result = taxonomy.classify(error)
        print(f"\nError: {error}")
        print(f"  Category: {result['category']}")
        print(f"  Severity: {result['severity']}")
        print(f"  Resolution: {result['resolution']}")
