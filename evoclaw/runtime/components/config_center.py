#!/usr/bin/env python3
"""
Configuration Center - Complete Implementation
Based on SYSTEM_FRAMEWORK_PROPOSAL.md Section 24
"""

import json
from pathlib import Path

from evoclaw.workspace_resolver import resolve_workspace
from typing import Dict, Any, Tuple
from datetime import datetime

WORKSPACE = resolve_workspace(__file__)
CONFIG_DIR = WORKSPACE / "evoclaw" / "runtime" / "config"


class ConfigCenter:
    """Configuration Center - manages all thresholds and weights"""
    
    def __init__(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        self.config_file = CONFIG_DIR / "runtime_config.json"
        self.config = self._load_or_create()
    
    def _load_or_create(self) -> Dict:
        """Load or create default config"""
        if self.config_file.exists():
            with open(self.config_file) as f:
                return json.load(f)
        
        # Default configuration
        default_config = {
            "environment": "dev",
            "config_version": f"cfg_{datetime.now().strftime('%Y%m%d')}_001",
            "routing_weights": {
                "w1": 0.20,  # rule_alignment
                "w2": 0.25,  # success_rate
                "w3": 0.15,  # rework_rate (penalty)
                "w4": 0.10,  # latency_penalty
                "w5": 0.15,  # trust_level
                "w6": 0.15   # scenario_match
            },
            "auto_execute_thresholds": {
                "routing_score_min": 0.75,
                "uncertainty_max": 0.3,
                "allowed_risk_levels": ["low"],
                "min_trust_level": "medium"
            },
            "review_thresholds": {
                "routing_score_min": 0.60,
                "routing_score_max": 0.75,
                "uncertainty_min": 0.3,
                "allowed_risk_levels": ["medium"]
            },
            "canary_thresholds": {
                "max_fail_rate_delta": 0.15,
                "min_sample_size": 50,
                "observation_window_minutes": 60
            },
            "rollback_thresholds": {
                "rework_rate_delta": 0.2,
                "repeat_error_rate_delta": 0.1,
                "success_rate_delta": -0.15
            },
            "promotion_thresholds": {
                "min_occurrences": 3,
                "max_validation_days": 7,
                "success_threshold": 0.7,
                "max_rework_rate": 0.15
            }
        }
        
        self._save(default_config)
        return default_config
    
    def _save(self, config: Dict):
        with open(self.config_file, "w") as f:
            json.dump(config, f, indent=2)
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get config value"""
        keys = key.split(".")
        value = self.config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
        return value if value is not None else default
    
    def set(self, key: str, value: Any):
        """Set config value"""
        keys = key.split(".")
        config = self.config
        for k in keys[:-1]:
            config = config.setdefault(k, {})
        config[keys[-1]] = value
        self._save(self.config)
    
    def get_routing_weights(self) -> Dict:
        return self.config.get("routing_weights", {})
    
    def get_auto_execute_thresholds(self) -> Dict:
        return self.config.get("auto_execute_thresholds", {})
    
    def can_auto_execute(self, routing_score: float, uncertainty: float, risk_level: str, trust_level: str) -> Tuple[bool, str]:
        """Check if task can auto execute"""
        
        thresholds = self.get_auto_execute_thresholds()
        
        if routing_score < thresholds.get("routing_score_min", 0.75):
            return False, f"routing_score {routing_score} < {thresholds['routing_score_min']}"
        
        if uncertainty > thresholds.get("uncertainty_max", 0.3):
            return False, f"uncertainty {uncertainty} > {thresholds['uncertainty_max']}"
        
        allowed = thresholds.get("allowed_risk_levels", ["low"])
        if risk_level not in allowed:
            return False, f"risk_level {risk_level} not in {allowed}"
        
        min_trust = thresholds.get("min_trust_level", "medium")
        trust_levels = ["unverified", "low", "medium", "high"]
        if trust_levels.index(trust_level) > trust_levels.index(min_trust):
            return False, f"trust_level {trust_level} < {min_trust}"
        
        return True, "auto execute allowed"
    
    def requires_review(self, routing_score: float, uncertainty: float, risk_level: str) -> Tuple[bool, str]:
        """Check if task requires review"""
        
        thresholds = self.get("review_thresholds", {})
        
        if routing_score >= thresholds.get("routing_score_min", 0.60):
            return False, "no review needed"
        
        return True, "review required"


# Global instance
_config = None

def get_config() -> ConfigCenter:
    global _config
    if _config is None:
        _config = ConfigCenter()
    return _config


if __name__ == "__main__":
    config = ConfigCenter()
    
    print("=== Current Configuration ===")
    print(f"Environment: {config.get('environment')}")
    print(f"Version: {config.get('config_version')}")
    print(f"\nRouting Weights: {config.get_routing_weights()}")
    print(f"\nAuto Execute Thresholds: {config.get_auto_execute_thresholds()}")
    
    print("\n=== Auto Execute Check ===")
    can_auto, reason = config.can_auto_execute(0.80, 0.2, "low", "medium")
    print(f"Can auto execute: {can_auto} ({reason})")
    
    can_auto, reason = config.can_auto_execute(0.70, 0.4, "medium", "low")
    print(f"Can auto execute: {can_auto} ({reason})")
