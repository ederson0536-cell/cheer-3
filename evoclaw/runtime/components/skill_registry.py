#!/usr/bin/env python3
"""
Complete Skill Registry - Full Implementation
Based on SYSTEM_FRAMEWORK_PROPOSAL.md Section 10-14
"""

import json
from pathlib import Path

from evoclaw.workspace_resolver import resolve_workspace
from datetime import datetime
from typing import Dict, List, Optional, Tuple

WORKSPACE = resolve_workspace(__file__)
REGISTRY_PATH = WORKSPACE / "evoclaw" / "runtime" / "skills_registry"


class CompleteSkillRegistry:
    """Complete Skill Registry with metadata and performance tracking"""
    
    def __init__(self):
        REGISTRY_PATH.mkdir(parents=True, exist_ok=True)
        self.registry_file = REGISTRY_PATH / "registry.json"
        self.skills = self._load_registry()
        
        if not self.skills:
            self.skills = self._get_default_skills()
            self._save_registry()
    
    def _load_registry(self) -> Dict:
        if self.registry_file.exists():
            with open(self.registry_file) as f:
                return json.load(f)
        return {}
    
    def _save_registry(self):
        with open(self.registry_file, "w") as f:
            json.dump(self.skills, f, indent=2, ensure_ascii=False)
    
    def _get_default_skills(self) -> Dict:
        """Default skill registry with full metadata"""
        return {
            "web_fetch": {
                "skill_id": "web_fetch",
                "skill_name": "Web Fetch",
                "domain": "research",
                "description": "Fetch data from web APIs and pages",
                "supported_task_types": ["research", "information"],
                "supported_subtask_types": ["fetch"],
                "supported_scenarios": ["news_search", "weather_query", "web_scrape"],
                "required_tools": ["curl", "wget", "requests"],
                "writable_scope": None,
                "read_only": True,
                "risk_profile": "low",
                "trust_level": "high",
                "compatible_rules": ["verify_source", "cite_sources"],
                "incompatible_rules": [],
                "capabilities": ["http_get", "http_post", "parse_json", "parse_html"],
                "performance": {
                    "avg_success_rate": 0.92,
                    "avg_latency_ms": 3000,
                    "avg_rework_rate": 0.05,
                    "total_executions": 0
                },
                "failure_modes": ["network_timeout", "auth_error", "parse_error"],
                "metadata": {
                    "version": "1.0",
                    "author": "system",
                    "created_at": datetime.now().isoformat()
                }
            },
            "weather_api": {
                "skill_id": "weather_api",
                "skill_name": "Weather API",
                "domain": "information",
                "description": "Query weather information from APIs",
                "supported_task_types": ["information"],
                "supported_subtask_types": ["fetch"],
                "supported_scenarios": ["weather_query"],
                "required_tools": ["curl", "wttr"],
                "writable_scope": None,
                "read_only": True,
                "risk_profile": "low",
                "trust_level": "high",
                "compatible_rules": ["verify_source"],
                "incompatible_rules": [],
                "capabilities": ["query_weather", "forecast"],
                "performance": {
                    "avg_success_rate": 0.95,
                    "avg_latency_ms": 2000,
                    "avg_rework_rate": 0.02,
                    "total_executions": 0
                },
                "failure_modes": ["api_error", "location_not_found"],
                "metadata": {"version": "1.0", "created_at": datetime.now().isoformat()}
            },
            "notion_api": {
                "skill_id": "notion_api",
                "skill_name": "Notion API",
                "domain": "automation",
                "description": "Interact with Notion workspace",
                "supported_task_types": ["writing", "automation"],
                "supported_subtask_types": ["write_output", "coordinate"],
                "supported_scenarios": ["notion_update", "notion_create"],
                "required_tools": ["notion_client", "api"],
                "writable_scope": ["notion_pages"],
                "read_only": False,
                "risk_profile": "medium",
                "trust_level": "medium",
                "compatible_rules": ["verify_format", "backup_before"],
                "incompatible_rules": [],
                "capabilities": ["create_page", "update_block", "append_children"],
                "performance": {
                    "avg_success_rate": 0.88,
                    "avg_latency_ms": 4000,
                    "avg_rework_rate": 0.10,
                    "total_executions": 0
                },
                "failure_modes": ["auth_error", "rate_limit", "invalid_block"],
                "metadata": {"version": "1.0", "created_at": datetime.now().isoformat()}
            },
            "cron_scheduler": {
                "skill_id": "cron_scheduler",
                "skill_name": "Cron Scheduler",
                "domain": "automation",
                "description": "Schedule automated tasks",
                "supported_task_types": ["automation", "planning"],
                "supported_subtask_types": ["coordinate", "schedule"],
                "supported_scenarios": ["scheduled_task", "cron_job"],
                "required_tools": ["crontab", "systemd"],
                "writable_scope": ["cron.d", "systemd_timers"],
                "read_only": False,
                "risk_profile": "high",
                "trust_level": "medium",
                "compatible_rules": ["backup_before", "log_actions", "rollback_capability"],
                "incompatible_rules": [],
                "capabilities": ["create_cron", "delete_cron", "list_crons"],
                "performance": {
                    "avg_success_rate": 0.82,
                    "avg_latency_ms": 3000,
                    "avg_rework_rate": 0.15,
                    "total_executions": 0
                },
                "failure_modes": ["syntax_error", "permission_denied"],
                "metadata": {"version": "1.0", "created_at": datetime.now().isoformat()}
            },
            "filesystem": {
                "skill_id": "filesystem",
                "skill_name": "Filesystem Operations",
                "domain": "engineering",
                "description": "Read, write, and manage files",
                "supported_task_types": ["coding", "writing"],
                "supported_subtask_types": ["edit_file", "write_output"],
                "supported_scenarios": ["code_edit", "file_write"],
                "required_tools": ["read", "write", "edit"],
                "writable_scope": ["workspace/*", "scripts/*"],
                "read_only": False,
                "risk_profile": "medium",
                "trust_level": "high",
                "compatible_rules": ["preserve_original", "backup_before"],
                "incompatible_rules": ["no_delete_system"],
                "capabilities": ["read_file", "write_file", "edit_file", "list_dir"],
                "performance": {
                    "avg_success_rate": 0.90,
                    "avg_latency_ms": 1000,
                    "avg_rework_rate": 0.08,
                    "total_executions": 0
                },
                "failure_modes": ["permission_denied", "file_not_found", "disk_full"],
                "metadata": {"version": "1.0", "created_at": datetime.now().isoformat()}
            },
            "browser": {
                "skill_id": "browser",
                "skill_name": "Browser Automation",
                "domain": "research",
                "description": "Automate browser interactions",
                "supported_task_types": ["research", "automation"],
                "supported_subtask_types": ["fetch", "analyze"],
                "supported_scenarios": ["web_automation", "form_fill"],
                "required_tools": ["playwright", "selenium"],
                "writable_scope": None,
                "read_only": True,
                "risk_profile": "medium",
                "trust_level": "medium",
                "compatible_rules": ["verify_page_load"],
                "incompatible_rules": [],
                "capabilities": ["navigate", "click", "type", "screenshot"],
                "performance": {
                    "avg_success_rate": 0.85,
                    "avg_latency_ms": 8000,
                    "avg_rework_rate": 0.15,
                    "total_executions": 0
                },
                "failure_modes": ["element_not_found", "timeout", "page_crash"],
                "metadata": {"version": "1.0", "created_at": datetime.now().isoformat()}
            },
            "code_analysis": {
                "skill_id": "code_analysis",
                "skill_name": "Code Analysis",
                "domain": "engineering",
                "description": "Analyze and review code",
                "supported_task_types": ["coding", "analysis"],
                "supported_subtask_types": ["analyze", "validate"],
                "supported_scenarios": ["code_review", "bug_analysis"],
                "required_tools": ["grep", "ast", "linter"],
                "writable_scope": None,
                "read_only": True,
                "risk_profile": "low",
                "trust_level": "high",
                "compatible_rules": ["verify_syntax"],
                "incompatible_rules": [],
                "capabilities": ["lint", "find_bugs", "analyze_complexity"],
                "performance": {
                    "avg_success_rate": 0.88,
                    "avg_latency_ms": 5000,
                    "avg_rework_rate": 0.05,
                    "total_executions": 0
                },
                "failure_modes": ["parse_error", "large_file"],
                "metadata": {"version": "1.0", "created_at": datetime.now().isoformat()}
            },
            "tts": {
                "skill_id": "tts",
                "skill_name": "Text to Speech",
                "domain": "communication",
                "description": "Convert text to speech",
                "supported_task_types": ["writing", "information"],
                "supported_subtask_types": ["write_output"],
                "supported_scenarios": ["voice_output"],
                "required_tools": ["elevenlabs", "gtts"],
                "writable_scope": None,
                "read_only": True,
                "risk_profile": "low",
                "trust_level": "high",
                "compatible_rules": [],
                "incompatible_rules": [],
                "capabilities": ["text_to_speech", "voice_generation"],
                "performance": {
                    "avg_success_rate": 0.95,
                    "avg_latency_ms": 5000,
                    "avg_rework_rate": 0.02,
                    "total_executions": 0
                },
                "failure_modes": ["api_error", "voice_not_found"],
                "metadata": {"version": "1.0", "created_at": datetime.now().isoformat()}
            }
        }
    
    def get_skill(self, skill_id: str) -> Optional[Dict]:
        return self.skills.get(skill_id)
    
    def get_skills_for_task(self, task_type: str) -> List[Dict]:
        return [s for s in self.skills.values() if task_type in s.get("supported_task_types", [])]
    
    def update_performance(self, skill_id: str, success: bool, latency_ms: float, rework: bool = False):
        if skill_id not in self.skills:
            return
        
        skill = self.skills[skill_id]
        perf = skill["performance"]
        
        # EMA update
        alpha = 0.1
        perf["avg_success_rate"] = perf["avg_success_rate"] * (1-alpha) + (1.0 if success else 0) * alpha
        perf["avg_latency_ms"] = perf["avg_latency_ms"] * (1-alpha) + latency_ms * alpha
        perf["avg_rework_rate"] = perf["avg_rework_rate"] * (1-alpha) + (1.0 if rework else 0) * alpha
        perf["total_executions"] += 1
        
        self._save_registry()
    
    def can_use_skill(self, skill_id: str, task_type: str, risk_level: str) -> Tuple[bool, str]:
        """Check if skill can be used"""
        
        skill = self.skills.get(skill_id)
        if not skill:
            return False, "Skill not found"
        
        # Check trust level vs risk
        trust_levels = {"unverified": 0, "low": 1, "medium": 2, "high": 3}
        risk_levels = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        
        trust = trust_levels.get(skill.get("trust_level", "low"), 0)
        risk = risk_levels.get(risk_level, 0)
        
        if risk > trust + 1:
            return False, f"Risk {risk_level} too high for trust {skill.get('trust_level')}"
        
        # Check if skill supports task type
        if task_type not in skill.get("supported_task_types", []):
            return False, f"Skill doesn't support task type {task_type}"
        
        return True, "Allowed"


# Global instance
_registry = None

def get_registry() -> CompleteSkillRegistry:
    global _registry
    if _registry is None:
        _registry = CompleteSkillRegistry()
    return _registry


if __name__ == "__main__":
    reg = get_registry()
    
    print("=== Skill Registry ===")
    print(f"Total skills: {len(reg.skills)}")
    
    for skill_id, skill in reg.skills.items():
        perf = skill.get("performance", {})
        print(f"\n{skill_id}:")
        print(f"  Trust: {skill['trust_level']}, Risk: {skill['risk_profile']}")
        print(f"  Success: {perf.get('avg_success_rate', 0):.0%}, Executions: {perf.get('total_executions', 0)}")
