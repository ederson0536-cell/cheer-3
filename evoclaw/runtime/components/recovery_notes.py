#!/usr/bin/env python3
"""
Recovery Notes - 恢复笔记
记录错误、问题、修复方案，用于系统恢复和知识积累
"""

import json
from pathlib import Path

from evoclaw.workspace_resolver import resolve_workspace
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum

WORKSPACE = resolve_workspace(__file__)
RECOVERY_DIR = WORKSPACE / "memory" / "recovery"


class IssueSeverity(Enum):
    """问题严重性"""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IssueStatus(Enum):
    """问题状态"""
    OPEN = "open"
    INVESTIGATING = "investigating"
    FIXED = "fixed"
    WORKAROUND = "workaround"
    WONT_FIX = "wont_fix"


class RecoveryNotes:
    """恢复笔记"""
    
    def __init__(self):
        RECOVERY_DIR.mkdir(parents=True, exist_ok=True)
        self.issues_file = RECOVERY_DIR / "issues.jsonl"
        self.solutions_file = RECOVERY_DIR / "solutions.jsonl"
    
    def create_issue(
        self,
        title: str,
        description: str,
        severity: IssueSeverity,
        task_id: str = None,
        tags: List[str] = None
    ) -> str:
        """创建问题"""
        
        issue_id = f"issue_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        issue = {
            "id": issue_id,
            "title": title,
            "description": description,
            "severity": severity.value,
            "status": IssueStatus.OPEN.value,
            "task_id": task_id,
            "tags": tags or [],
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
            "root_cause": None,
            "solution_id": None,
            "related_issues": []
        }
        
        with open(self.issues_file, "a") as f:
            f.write(json.dumps(issue, ensure_ascii=False) + "\n")
        
        return issue_id
    
    def add_solution(
        self,
        issue_id: str,
        solution: str,
        worked: bool = None,
        notes: str = None
    ) -> str:
        """添加解决方案"""
        
        solution_id = f"sol_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        sol = {
            "id": solution_id,
            "issue_id": issue_id,
            "solution": solution,
            "worked": worked,
            "notes": notes,
            "created_at": datetime.now().isoformat(),
            "verified": False
        }
        
        with open(self.solutions_file, "a") as f:
            f.write(json.dumps(sol, ensure_ascii=False) + "\n")
        
        # 关联到问题
        self._link_solution(issue_id, solution_id)
        
        return solution_id
    
    def _link_solution(self, issue_id: str, solution_id: str):
        """关联解决方案到问题"""
        
        issues = []
        
        if self.issues_file.exists():
            with open(self.issues_file) as f:
                for line in f:
                    issue = json.loads(line)
                    if issue["id"] == issue_id:
                        issue["solution_id"] = solution_id
                        issue["status"] = IssueStatus.FIXED.value if issue.get("worked") else IssueStatus.WORKAROUND.value
                        issue["updated_at"] = datetime.now().isoformat()
                    issues.append(issue)
        
        with open(self.issues_file, "w") as f:
            for issue in issues:
                f.write(json.dumps(issue, ensure_ascii=False) + "\n")
    
    def get_open_issues(self, severity: IssueSeverity = None) -> List[Dict]:
        """获取开放问题"""
        
        issues = []
        
        if not self.issues_file.exists():
            return issues
        
        with open(self.issues_file) as f:
            for line in f:
                issue = json.loads(line)
                if issue["status"] in [IssueStatus.OPEN.value, IssueStatus.INVESTIGATING.value]:
                    if severity is None or issue["severity"] == severity.value:
                        issues.append(issue)
        
        # 按严重性排序
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        issues.sort(key=lambda x: severity_order.get(x["severity"], 4))
        
        return issues
    
    def get_issue_solutions(self, issue_id: str) -> List[Dict]:
        """获取问题的解决方案"""
        
        solutions = []
        
        if not self.solutions_file.exists():
            return solutions
        
        with open(self.solutions_file) as f:
            for line in f:
                sol = json.loads(line)
                if sol["issue_id"] == issue_id:
                    solutions.append(sol)
        
        return solutions
    
    def search_issues(self, keyword: str) -> List[Dict]:
        """搜索问题"""
        
        results = []
        
        if not self.issues_file.exists():
            return results
        
        with open(self.issues_file) as f:
            for line in f:
                issue = json.loads(line)
                if (keyword.lower() in issue.get("title", "").lower() or
                    keyword.lower() in issue.get("description", "").lower()):
                    results.append(issue)
        
        return results
    
    def get_statistics(self) -> Dict:
        """获取统计"""
        
        stats = {
            "total_issues": 0,
            "open": 0,
            "fixed": 0,
            "by_severity": {},
            "common_tags": {}
        }
        
        if not self.issues_file.exists():
            return stats
        
        tag_counts = {}
        
        with open(self.issues_file) as f:
            for line in f:
                issue = json.loads(line)
                stats["total_issues"] += 1
                
                if issue["status"] == IssueStatus.OPEN.value:
                    stats["open"] += 1
                elif issue["status"] == IssueStatus.FIXED.value:
                    stats["fixed"] += 1
                
                severity = issue.get("severity", "unknown")
                stats["by_severity"][severity] = stats["by_severity"].get(severity, 0) + 1
                
                for tag in issue.get("tags", []):
                    tag_counts[tag] = tag_counts.get(tag, 0) + 1
        
        # 常用标签
        stats["common_tags"] = dict(
            sorted(tag_counts.items(), key=lambda x: -x[1])[:10]
        )
        
        return stats


# 全局实例
_recovery = None

def get_recovery() -> RecoveryNotes:
    global _recovery
    if _recovery is None:
        _recovery = RecoveryNotes()
    return _recovery


if __name__ == "__main__":
    recovery = get_recovery()
    
    # Test
    issue_id = recovery.create_issue(
        "测试问题",
        "这是一个测试问题",
        IssueSeverity.MEDIUM,
        tags=["test", "demo"]
    )
    
    print(f"Created: {issue_id}")
    print(f"Open issues: {len(recovery.get_open_issues())}")
    print(f"Stats: {recovery.get_statistics()}")
