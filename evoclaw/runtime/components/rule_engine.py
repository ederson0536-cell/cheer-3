#!/usr/bin/env python3
"""
Rule System - Complete Implementation
Based on SYSTEM_FRAMEWORK_PROPOSAL.md
P0-P4 Priority System
"""

import json
import sqlite3
from pathlib import Path

from evoclaw.workspace_resolver import resolve_workspace
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from enum import Enum

WORKSPACE = resolve_workspace(__file__)

class RulePriority(Enum):
    """Rule Priority Levels"""
    P0_HARD = "P0"      # Cannot be overridden
    P1_GOVERNANCE = "P1" # Requires governance approval
    P2_TASK_TYPE = "P2"  # Applies to task types
    P3_SCENARIO = "P3"   # Applies to scenarios
    P4_SUGGESTION = "P4"  # Suggestions only


class RuleEngine:
    """Complete Rule Engine with P0-P4 priority"""
    
    def __init__(self):
        self.rules_dir = WORKSPACE / "evoclaw" / "runtime" / "rules"
        self.rules_dir.mkdir(parents=True, exist_ok=True)
        self.active_rules_dir = WORKSPACE / "memory" / "rules" / "active"
        self.memory_db = WORKSPACE / "memory" / "memory.db"
        
        # Load rule definitions
        self.rules = self._load_rules()

    def _rules_columns(self) -> set:
        """Return existing columns for rules table."""
        if not self.memory_db.exists():
            return set()
        try:
            with sqlite3.connect(self.memory_db) as conn:
                rows = conn.execute("PRAGMA table_info(rules)").fetchall()
            return {str(row[1]) for row in rows}
        except Exception:
            return set()

    def _load_dynamic_rules(self) -> List[Dict]:
        """Load active rules from SQLite first, then fall back to file cache."""
        rules: List[Dict] = []

        # Source 1: SQLite
        if self.memory_db.exists():
            try:
                cols = self._rules_columns()
                select_cols = [
                    "id",
                    "content",
                    "source_proposal_id",
                    "created_at",
                    "enabled",
                ]
                if "priority" in cols:
                    select_cols.append("priority")
                if "scope" in cols:
                    select_cols.append("scope")
                if "action" in cols:
                    select_cols.append("action")

                with sqlite3.connect(self.memory_db) as conn:
                    conn.row_factory = sqlite3.Row
                    rows = conn.execute(
                        f"SELECT {', '.join(select_cols)} FROM rules WHERE enabled = 1"
                    ).fetchall()

                for row in rows:
                    payload = {}
                    content_raw = row["content"]
                    if content_raw:
                        try:
                            payload = json.loads(content_raw)
                        except Exception:
                            payload = {"text": content_raw}
                    scope = row["scope"] if "scope" in row.keys() else ""
                    if scope:
                        try:
                            parsed_scope = json.loads(scope)
                            if isinstance(parsed_scope, dict):
                                payload = {**parsed_scope, **payload}
                            else:
                                payload["scope"] = scope
                        except Exception:
                            payload["scope"] = scope
                    rules.append(
                        {
                            "id": row["id"],
                            "source_proposal_id": row["source_proposal_id"],
                            "created_at": row["created_at"],
                            "enabled": bool(row["enabled"]),
                            "priority": (
                                row["priority"] if "priority" in row.keys() else payload.get("priority")
                            ),
                            "action": (
                                row["action"] if "action" in row.keys() else payload.get("action")
                            ),
                            **(payload if isinstance(payload, dict) else {"text": str(payload)}),
                        }
                    )
            except Exception:
                pass

        if rules:
            return rules

        # Source 2: memory/rules/active/*.json (fallback)
        if not self.active_rules_dir.exists():
            return []
        for rule_file in sorted(self.active_rules_dir.glob("*.json")):
            try:
                with open(rule_file, "r", encoding="utf-8") as f:
                    payload = json.load(f)
                if not isinstance(payload, dict):
                    continue
                if not payload.get("enabled", True):
                    continue
                content = payload.get("content", {})
                if not isinstance(content, dict):
                    content = {"text": str(content)}
                rules.append(
                    {
                        "id": payload.get("id"),
                        "source_proposal_id": payload.get("source_proposal_id"),
                        "created_at": payload.get("created_at"),
                        "enabled": bool(payload.get("enabled", True)),
                        **content,
                    }
                )
            except Exception:
                continue
        return rules

    def _rule_active_now(self, rule: Dict) -> bool:
        now = datetime.now()
        start = str(rule.get("valid_from") or "").strip()
        end = str(rule.get("valid_until") or "").strip()

        if start:
            try:
                if datetime.fromisoformat(start) > now:
                    return False
            except ValueError:
                pass

        if end:
            try:
                if datetime.fromisoformat(end) < now:
                    return False
            except ValueError:
                pass

        return True

    def _match_scope(self, rule: Dict, task_type: str, risk_level: str, scenario: str) -> bool:
        scope_task = str(rule.get("task_type") or "").strip().lower()
        scope_scenario = str(rule.get("scenario") or "").strip().lower()
        scope_raw = str(rule.get("scope") or "").strip().lower()

        if not scope_task and scope_raw:
            # scope can be plain token (e.g. coding) or key-value (e.g. task_type:coding)
            if ":" in scope_raw:
                k, v = [p.strip() for p in scope_raw.split(":", 1)]
                if k in {"task", "task_type", "type"}:
                    scope_task = v
                elif k in {"scenario", "scene"}:
                    scope_scenario = v
            else:
                scope_task = scope_raw

        if scope_task and scope_task not in {"*", "all"} and scope_task != task_type.lower():
            return False
        if scope_scenario and scope_scenario not in {"*", "all"} and scope_scenario != scenario.lower():
            return False

        risk_levels = rule.get("risk_levels")
        if isinstance(risk_levels, list) and risk_levels:
            normalized = {str(v).lower() for v in risk_levels}
            if risk_level.lower() not in normalized:
                return False

        return self._rule_active_now(rule)

    def _group_dynamic_rules(self, task_type: str, risk_level: str, scenario: str) -> Dict[str, List[Dict]]:
        grouped = {
            "P0_HARD": [],
            "P1_GOVERNANCE": [],
            "P2_TASK_TYPE": [],
            "P3_SCENARIO": [],
            "P4_SUGGESTION": [],
        }
        dynamic_rules = self._load_dynamic_rules()

        for rule in dynamic_rules:
            if not self._match_scope(rule, task_type, risk_level, scenario):
                continue
            priority = str(rule.get("priority") or "P2_TASK_TYPE").upper()
            if priority in {"P0", "P0_HARD"}:
                grouped["P0_HARD"].append(rule)
            elif priority in {"P1", "P1_GOVERNANCE"}:
                grouped["P1_GOVERNANCE"].append(rule)
            elif priority in {"P3", "P3_SCENARIO"}:
                grouped["P3_SCENARIO"].append(rule)
            elif priority in {"P4", "P4_SUGGESTION"}:
                grouped["P4_SUGGESTION"].append(rule)
            else:
                grouped["P2_TASK_TYPE"].append(rule)

        return grouped
    
    def _load_rules(self) -> Dict:
        """Load all rules"""
        return {
            "P0_HARD": self._get_hard_rules(),
            "P1_GOVERNANCE": self._get_governance_rules(),
            "P2_TASK_TYPE": self._get_task_type_rules(),
            "P3_SCENARIO": self._get_scenario_rules(),
            "P4_SUGGESTION": self._get_suggestions()
        }
    
    def _get_hard_rules(self) -> List[Dict]:
        """P0 Hard Rules - Cannot be overridden"""
        return [
            {
                "id": "p0_001",
                "name": "private_data_stays_private",
                "description": "Private data must never be exfiltrated",
                "priority": "P0",
                "enforced": True
            },
            {
                "id": "p0_002", 
                "name": "no_unauthorized_write",
                "description": "Cannot write outside allowed file scope",
                "priority": "P0",
                "enforced": True
            },
            {
                "id": "p0_003",
                "name": "ask_before_external_actions",
                "description": "Must ask before sending emails, tweets, etc",
                "priority": "P0",
                "enforced": True
            },
            {
                "id": "p0_004",
                "name": "high_risk_requires_approval",
                "description": "High risk tasks require explicit approval",
                "priority": "P0",
                "enforced": True
            }
        ]
    
    def _get_governance_rules(self) -> List[Dict]:
        """P1 Governance Rules"""
        return [
            {
                "id": "p1_001",
                "name": "skill_trust_level_check",
                "description": "Low trust skills require governance approval",
                "priority": "P1"
            },
            {
                "id": "p1_002",
                "name": "candidate_promotion_requires_review",
                "description": "Candidate to Semantic requires governance review",
                "priority": "P1"
            },
            {
                "id": "p1_003",
                "name": "proposal_requires_approval",
                "description": "Proposals affecting P0/P1 require approval",
                "priority": "P1"
            }
        ]
    
    def _get_task_type_rules(self) -> Dict[str, List[Dict]]:
        """P2 Task Type Rules"""
        return {
            "research": [
                {"id": "p2_r001", "name": "verify_source", "rule": "Verify information source reliability"},
                {"id": "p2_r002", "name": "cite_sources", "rule": "Cite sources in output"},
                {"id": "p2_r003", "name": "cross_reference", "rule": "Cross-reference multiple sources"}
            ],
            "coding": [
                {"id": "p2_c001", "name": "preserve_original", "rule": "Preserve original code before changes"},
                {"id": "p2_c002", "name": "test_driven", "rule": "Use test-driven development"},
                {"id": "p2_c003", "name": "syntax_check", "rule": "Verify syntax after changes"}
            ],
            "automation": [
                {"id": "p2_a001", "name": "backup_before", "rule": "Create backup before automation"},
                {"id": "p2_a002", "name": "log_actions", "rule": "Log all automated actions"},
                {"id": "p2_a003", "name": "rollback_capability", "rule": "Include rollback capability"}
            ],
            "writing": [
                {"id": "p2_w001", "name": "verify_facts", "rule": "Verify facts before publishing"},
                {"id": "p2_w002", "name": "proofread", "rule": "Proofread before finish"}
            ]
        }
    
    def _get_scenario_rules(self) -> Dict[str, List[Dict]]:
        """P3 Scenario Rules"""
        return {
            "notion_update": [
                {"id": "p3_n001", "name": "verify_format", "rule": "Verify Notion block format"}
            ],
            "cron_setup": [
                {"id": "p3_c001", "name": "verify_cron", "rule": "Verify cron syntax"}
            ]
        }
    
    def _get_suggestions(self) -> List[Dict]:
        """P4 Suggestions"""
        return [
            {"id": "p4_001", "name": "use_cache", "rule": "Consider caching results"},
            {"id": "p4_002", "name": "log_performance", "rule": "Log performance metrics"}
        ]
    
    def get_rules_for_task(self, task_type: str, risk_level: str, scenario: str = "") -> Dict:
        """Get rules for a specific task"""
        
        result = {
            "P0_HARD": [],
            "P1_GOVERNANCE": [],
            "P2_TASK_TYPE": [],
            "P3_SCENARIO": [],
            "P4_SUGGESTION": []
        }
        
        # Always include P0 hard rules
        result["P0_HARD"] = self.rules["P0_HARD"]
        
        # P1 - based on risk
        if risk_level in ["high", "critical"]:
            result["P1_GOVERNANCE"] = self.rules["P1_GOVERNANCE"]
        
        # P2 - based on task type
        if task_type in self.rules["P2_TASK_TYPE"]:
            result["P2_TASK_TYPE"] = self.rules["P2_TASK_TYPE"][task_type]
        
        # P3 - based on scenario
        if scenario in self.rules["P3_SCENARIO"]:
            result["P3_SCENARIO"] = self.rules["P3_SCENARIO"][scenario]
        
        # P4 - suggestions (always available)
        result["P4_SUGGESTION"] = self.rules["P4_SUGGESTION"]

        # Dynamic active rules (from approved proposals)
        dynamic = self._group_dynamic_rules(task_type, risk_level, scenario)
        for bucket in result.keys():
            result[bucket].extend(dynamic.get(bucket, []))
        
        return result
    
    def check_conflicts(self, rules: Dict) -> List[Dict]:
        """Check for rule conflicts"""
        conflicts = []
        
        # P0 cannot be overridden
        for p0 in rules.get("P0_HARD", []):
            conflicts.append({
                "type": "hard_rule",
                "rule": p0["name"],
                "action": "MUST_ENFORCE"
            })
        
        return conflicts
    
    def resolve_conflict(self, rule1: Dict, rule2: Dict) -> Dict:
        """Resolve conflict using priority"""
        priority_order = ["P0", "P1", "P2", "P3", "P4"]
        
        p1 = priority_order.index(rule1.get("priority", "P4"))
        p2 = priority_order.index(rule2.get("priority", "P4"))
        
        if p1 <= p2:
            return rule1
        return rule2


# Global instance
_rule_engine = None

def get_rule_engine() -> RuleEngine:
    global _rule_engine
    if _rule_engine is None:
        _rule_engine = RuleEngine()
    return _rule_engine


if __name__ == "__main__":
    engine = RuleEngine()
    
    # Test
    rules = engine.get_rules_for_task("research", "low", "")
    
    print("=== Rules for research task (low risk) ===")
    for priority, rule_list in rules.items():
        print(f"\n{priority}:")
        for r in rule_list:
            print(f"  - {r['name']}: {r.get('rule', r.get('description', ''))}")
