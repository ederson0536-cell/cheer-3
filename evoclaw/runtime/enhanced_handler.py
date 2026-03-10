#!/usr/bin/env python3
"""
Enhanced Message Handler - With Execution
"""

import json
import sys
from datetime import datetime
from pathlib import Path

from evoclaw.workspace_resolver import resolve_workspace

WORKSPACE = resolve_workspace(__file__)
sys.path.insert(0, str(WORKSPACE / "evoclaw" / "runtime"))

from evoclaw_runtime import EvoClawRuntime
from components.task_engine import analyze_task
from components.skill_executor import get_executor


class EnhancedMessageHandler:
    """消息处理器 - 集成执行"""
    
    def __init__(self):
        self.runtime = EvoClawRuntime()
        self.executor = get_executor()
        self.state = {"active": False, "task_id": None}
        
    def handle(self, message: str) -> dict:
        """处理消息"""
        
        # 分析任务
        analysis = analyze_task(message)
        
        # 检查是否取消
        if any(w in message for w in ["取消", "cancel", "停止"]):
            if self.state["active"]:
                self.runtime.complete(error="用户取消")
                self.state = {"active": False, "task_id": None}
            return {"type": "cancelled", "message": "已取消"}
        
        # 检查是否完成
        if self.state["active"]:
            if any(w in message for w in ["完成", "好了", "done", "完成"]):
                result = self.runtime.complete_subtask(result=message)
                
                # 检查是否结束
                if len(self.runtime.state.get("subtasks", [])) >= 1:
                    self.runtime.complete(result=message)
                    self.state = {"active": False, "task_id": None}
                    return {"type": "completed", "message": "任务完成！"}
                
                return {"type": "subtask_done", "message": "子任务完成"}
        
        # 新任务
        if analysis["task_type"] in ["research", "coding", "automation", "writing", "information"]:
            # 启动任务
            self.runtime.start(message)
            
            # 确定子任务类型
            subtask_type = self._infer_subtask(analysis)
            
            # 执行
            self.runtime.execute_subtask(subtask_type, message[:50])
            
            # 实际执行技能
            skill = self._get_skill_id(analysis)
            exec_result = self.executor.execute(skill, {"goal": message})
            
            # 完成
            self.runtime.complete_subtask(result=str(exec_result))
            self.runtime.complete(result="完成")
            
            self.state = {"active": False, "task_id": None}
            
            return {
                "type": "executed",
                "task_type": analysis["task_type"],
                "skill": skill,
                "execution": exec_result,
                "message": f"任务完成！执行了 {skill}"
            }
        
        # 简单对话
        return {
            "type": "conversation",
            "message": f"收到: {message[:20]}..."
        }
    
    def _infer_subtask(self, analysis: dict) -> str:
        """推断子任务"""
        tags = analysis.get("tags", [])
        
        if any(t in tags for t in ["news", "search", "fetch"]):
            return "fetch"
        if any(t in tags for t in ["code", "script"]):
            return "edit_file"
        if any(t in tags for t in ["notion", "write"]):
            return "write_output"
        
        return "fetch"
    
    def _get_skill_id(self, analysis: dict) -> str:
        """获取技能ID"""
        task_type = analysis.get("task_type")
        
        mapping = {
            "research": "web_fetch_skill",
            "information": "weather_skill",
            "coding": "coding_editor",
            "automation": "cron_scheduler",
            "writing": "notion_api"
        }
        
        return mapping.get(task_type, "web_fetch_skill")


if __name__ == "__main__":
    handler = EnhancedMessageHandler()
    
    tests = [
        "今天天气怎么样",
        "帮我搜索科技新闻",
        "设置每天早上8点提醒",
        "帮我写个Python脚本"
    ]
    
    for msg in tests:
        print(f"\n=== {msg} ===")
        result = handler.handle(msg)
        print(f"Type: {result.get('type')}")
        if result.get('skill'):
            print(f"Skill: {result.get('skill')}")
        if result.get('execution'):
            print(f"Result: {result['execution'].get('message')}")
