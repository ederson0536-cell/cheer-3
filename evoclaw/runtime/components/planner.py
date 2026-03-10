#!/usr/bin/env python3
"""
Complete Task Decomposer - Based on SYSTEM_FRAMEWORK_PROPOSAL.md Section 7
With dependency modeling and complexity layers
"""

import json
from typing import List, Dict, Optional, Tuple
from datetime import datetime

# Task decomposition templates (Section 7.2)
TASK_TEMPLATES = {
    "research": {
        "L0": [
            {"type": "fetch", "goal": "Fetch information from source", "tool": "web_fetch", "depends_on": []}
        ],
        "L1": [
            {"type": "fetch", "goal": "Fetch primary source", "tool": "web_fetch", "depends_on": []},
            {"type": "validate", "goal": "Verify source reliability", "tool": "code_analysis", "depends_on": ["fetch"]}
        ],
        "L2": [
            {"type": "fetch", "goal": "Fetch primary sources", "tool": "web_fetch", "depends_on": []},
            {"type": "fetch", "goal": "Fetch secondary sources", "tool": "web_fetch", "depends_on": []},
            {"type": "analyze", "goal": "Cross-reference and analyze", "tool": "code_analysis", "depends_on": ["fetch"]},
            {"type": "validate", "goal": "Validate findings", "tool": "code_analysis", "depends_on": ["analyze"]}
        ]
    },
    "coding": {
        "L0": [
            {"type": "analyze", "goal": "Understand requirements", "tool": "code_analysis", "depends_on": []},
            {"type": "edit", "goal": "Make code changes", "tool": "filesystem", "depends_on": ["analyze"]}
        ],
        "L1": [
            {"type": "analyze", "goal": "Analyze requirements", "tool": "code_analysis", "depends_on": []},
            {"type": "backup", "goal": "Backup original files", "tool": "filesystem", "depends_on": ["analyze"]},
            {"type": "edit", "goal": "Implement changes", "tool": "filesystem", "depends_on": ["backup"]},
            {"type": "validate", "goal": "Validate syntax", "tool": "code_analysis", "depends_on": ["edit"]}
        ],
        "L2": [
            {"type": "analyze", "goal": "Analyze requirements", "tool": "code_analysis", "depends_on": []},
            {"type": "plan", "goal": "Design solution", "tool": "filesystem", "depends_on": ["analyze"]},
            {"type": "backup", "goal": "Backup original", "tool": "filesystem", "depends_on": ["plan"]},
            {"type": "edit", "goal": "Implement core logic", "tool": "filesystem", "depends_on": ["backup"]},
            {"type": "test", "goal": "Write tests", "tool": "filesystem", "depends_on": ["edit"]},
            {"type": "validate", "goal": "Run tests", "tool": "code_analysis", "depends_on": ["test"]}
        ]
    },
    "automation": {
        "L0": [
            {"type": "analyze", "goal": "Analyze automation requirements", "tool": "code_analysis", "depends_on": []},
            {"type": "implement", "goal": "Implement automation", "tool": "filesystem", "depends_on": ["analyze"]}
        ],
        "L1": [
            {"type": "analyze", "goal": "Analyze requirements", "tool": "code_analysis", "depends_on": []},
            {"type": "backup", "goal": "Backup current state", "tool": "filesystem", "depends_on": ["analyze"]},
            {"type": "implement", "goal": "Implement automation", "tool": "filesystem", "depends_on": ["backup"]},
            {"type": "test", "goal": "Test automation", "tool": "filesystem", "depends_on": ["implement"]},
            {"type": "schedule", "goal": "Set up schedule", "tool": "cron_scheduler", "depends_on": ["test"]}
        ],
        "L2": [
            {"type": "analyze", "goal": "Full analysis", "tool": "code_analysis", "depends_on": []},
            {"type": "design", "goal": "Design workflow", "tool": "filesystem", "depends_on": ["analyze"]},
            {"type": "backup", "goal": "Full backup", "tool": "filesystem", "depends_on": ["design"]},
            {"type": "implement", "goal": "Implement core", "tool": "filesystem", "depends_on": ["backup"]},
            {"type": "test", "goal": "Comprehensive test", "tool": "filesystem", "depends_on": ["implement"]},
            {"type": "validate", "goal": "Validate results", "tool": "code_analysis", "depends_on": ["test"]},
            {"type": "schedule", "goal": "Configure schedule", "tool": "cron_scheduler", "depends_on": ["validate"]}
        ]
    },
    "writing": {
        "L0": [
            {"type": "fetch", "goal": "Gather information", "tool": "web_fetch", "depends_on": []},
            {"type": "write", "goal": "Write content", "tool": "filesystem", "depends_on": ["fetch"]}
        ],
        "L1": [
            {"type": "fetch", "goal": "Gather information", "tool": "web_fetch", "depends_on": []},
            {"type": "outline", "goal": "Create outline", "tool": "filesystem", "depends_on": ["fetch"]},
            {"type": "write", "goal": "Write content", "tool": "filesystem", "depends_on": ["outline"]},
            {"type": "review", "goal": "Proofread", "tool": "code_analysis", "depends_on": ["write"]}
        ],
        "L2": [
            {"type": "fetch", "goal": "Research sources", "tool": "web_fetch", "depends_on": []},
            {"type": "analyze", "goal": "Analyze content", "tool": "code_analysis", "depends_on": ["fetch"]},
            {"type": "outline", "goal": "Create detailed outline", "tool": "filesystem", "depends_on": ["analyze"]},
            {"type": "write", "goal": "Write draft", "tool": "filesystem", "depends_on": ["outline"]},
            {"type": "review", "goal": "Internal review", "tool": "code_analysis", "depends_on": ["write"]},
            {"type": "edit", "goal": "Final edits", "tool": "filesystem", "depends_on": ["review"]},
            {"type": "publish", "goal": "Publish output", "tool": "notion_api", "depends_on": ["edit"]}
        ]
    },
    "information": {
        "L0": [
            {"type": "fetch", "goal": "Query information", "tool": "weather_api", "depends_on": []}
        ],
        "L1": [
            {"type": "fetch", "goal": "Get primary data", "tool": "web_fetch", "depends_on": []},
            {"type": "format", "goal": "Format output", "tool": "filesystem", "depends_on": ["fetch"]}
        ],
        "L2": [
            {"type": "fetch", "goal": "Get multiple sources", "tool": "web_fetch", "depends_on": []},
            {"type": "analyze", "goal": "Cross-reference", "tool": "code_analysis", "depends_on": ["fetch"]},
            {"type": "format", "goal": "Format for display", "tool": "filesystem", "depends_on": ["analyze"]}
        ]
    }
}


class CompleteTaskDecomposer:
    """Complete Task Decomposer with dependency modeling"""
    
    def __init__(self):
        self.templates = TASK_TEMPLATES
    
    def decompose(
        self,
        task_type: str,
        complexity: str,
        context: Dict = None
    ) -> Dict:
        """Decompose task into subtasks with dependencies"""
        
        context = context or {}
        
        # Get template
        template_map = self.templates.get(task_type, self.templates.get("research"))
        subtask_defs = template_map.get(complexity, template_map.get("L0"))
        
        # Generate subtasks
        subtasks = []
        subtask_map = {}  # id -> subtask
        
        for i, defn in enumerate(subtask_defs):
            subtask_id = f"st_{i+1:03d}"
            
            subtask = {
                "subtask_id": subtask_id,
                "type": defn["type"],
                "goal": defn["goal"],
                "tool": defn["tool"],
                "depends_on": defn.get("depends_on", []),
                "status": "pending",
                "done_criteria": self._get_done_criteria(defn["type"]),
                "estimated_duration": self._estimate_duration(defn["type"])
            }
            
            subtasks.append(subtask)
            subtask_map[defn["type"]] = subtask_id
        
        # Resolve dependencies
        resolved_subtasks = self._resolve_dependencies(subtasks)
        
        # Calculate execution order (topological sort)
        execution_order = self._topological_sort(resolved_subtasks)
        
        # Determine if parallel execution possible
        can_parallel = self._can_execute_in_parallel(resolved_subtasks)
        
        plan = {
            "task_id": context.get("task_id", "unknown"),
            "task_type": task_type,
            "complexity": complexity,
            "total_subtasks": len(resolved_subtasks),
            "subtasks": resolved_subtasks,
            "execution_order": execution_order,
            "can_parallel": can_parallel,
            "total_estimated_duration": sum(s.get("estimated_duration", 0) for s in resolved_subtasks),
            "parallel_groups": self._group_for_parallel(resolved_subtasks) if can_parallel else [],
            "created_at": datetime.now().isoformat()
        }
        
        return plan
    
    def _resolve_dependencies(self, subtasks: List[Dict]) -> List[Dict]:
        """Resolve dependency references to subtask IDs"""
        
        type_to_id = {s["type"]: s["subtask_id"] for s in subtasks}
        
        for subtask in subtasks:
            resolved_deps = []
            for dep_type in subtask.get("depends_on", []):
                if dep_type in type_to_id:
                    resolved_deps.append(type_to_id[dep_type])
            subtask["dependencies"] = resolved_deps
            subtask["pending_dependencies"] = resolved_deps.copy()
        
        return subtasks
    
    def _topological_sort(self, subtasks: List[Dict]) -> List[str]:
        """Generate execution order"""
        
        # Simple BFS-based topological sort
        in_degree = {s["subtask_id"]: len(s.get("dependencies", [])) for s in subtasks}
        
        queue = [s["subtask_id"] for s in subtasks if in_degree[s["subtask_id"]] == 0]
        order = []
        
        while queue:
            current = queue.pop(0)
            order.append(current)
            
            # Reduce in-degree for dependents
            for subtask in subtasks:
                if current in subtask.get("pending_dependencies", []):
                    in_degree[subtask["subtask_id"]] -= 1
                    if in_degree[subtask["subtask_id"]] == 0:
                        queue.append(subtask["subtask_id"])
        
        return order
    
    def _can_execute_in_parallel(self, subtasks: List[Dict]) -> bool:
        """Check if any subtasks can run in parallel"""
        
        # If there's dependencies, cannot fully parallelize
        for s in subtasks:
            if s.get("dependencies"):
                return False
        
        # Multiple independent tasks can run in parallel
        return len(subtasks) >= 3
    
    def _group_for_parallel(self, subtasks: List[Dict]) -> List[List[str]]:
        """Group subtasks that can run in parallel"""
        
        groups = []
        current_group = []
        
        for subtask in subtasks:
            if not subtask.get("dependencies"):
                current_group.append(subtask["subtask_id"])
            else:
                if current_group:
                    groups.append(current_group)
                    current_group = []
                groups.append([subtask["subtask_id"]])
        
        if current_group:
            groups.append(current_group)
        
        return groups
    
    def _get_done_criteria(self, subtask_type: str) -> List[str]:
        """Get done criteria for subtask type"""
        
        criteria = {
            "fetch": ["Data fetched successfully", "Source verified"],
            "analyze": ["Analysis complete", "Key findings identified"],
            "validate": ["Validation passed", "No errors found"],
            "edit": ["Changes applied", "Syntax valid"],
            "write": ["Content written", "Format correct"],
            "test": ["Tests passed", "No failures"],
            "schedule": ["Schedule configured", "Cron syntax valid"],
            "backup": ["Backup created", "Restore point set"],
            "plan": ["Plan documented", "Steps defined"],
            "outline": ["Outline complete", "Structure logical"],
            "review": ["Review complete", "Feedback incorporated"],
            "format": ["Format correct", "Output readable"],
            "publish": ["Published successfully", "Accessible"]
        }
        
        return criteria.get(subtask_type, ["Completed"])
    
    def _estimate_duration(self, subtask_type: str) -> int:
        """Estimate duration in seconds"""
        
        durations = {
            "fetch": 30,
            "analyze": 60,
            "validate": 30,
            "edit": 120,
            "write": 120,
            "test": 60,
            "schedule": 30,
            "backup": 30,
            "plan": 60,
            "outline": 30,
            "review": 30,
            "format": 15,
            "publish": 30,
            "design": 120,
            "implement": 180,
            "edit": 120
        }
        
        return durations.get(subtask_type, 60)


# Global instance
_decomposer = None

def get_decomposer() -> CompleteTaskDecomposer:
    global _decomposer
    if _decomposer is None:
        _decomposer = CompleteTaskDecomposer()
    return _decomposer


if __name__ == "__main__":
    decomposer = CompleteTaskDecomposer()
    
    tests = [
        ("research", "L0"),
        ("research", "L1"),
        ("research", "L2"),
        ("coding", "L2"),
        ("automation", "L1")
    ]
    
    for task_type, complexity in tests:
        print(f"\n=== {task_type} / {complexity} ===")
        plan = decomposer.decompose(task_type, complexity, {"task_id": "t_001"})
        print(f"Subtasks: {plan['total_subtasks']}")
        print(f"Can parallel: {plan['can_parallel']}")
        print(f"Order: {plan['execution_order']}")
        for st in plan["subtasks"]:
            print(f"  - {st['subtask_id']}: {st['type']} (deps: {st.get('dependencies', [])})")
