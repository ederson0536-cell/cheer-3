#!/usr/bin/env python3
"""
Task Understanding Engine
Analyzes incoming tasks and generates structured understanding
"""

import json
import re
from datetime import datetime
from typing import Dict, List, Optional
import uuid

# Task type keywords mapping
TASK_TYPE_KEYWORDS = {
    "coding": ["代码", "开发", "写", "修改", "debug", "fix", "implement", "create", "code", "script", "函数", "API"],
    "research": ["搜索", "查询", "研究", "看看", "有什么", "找找", "看看有什么", "git", "GitHub", "找找", "看看有什么", "调研", "找", "获取", "fetch", "search", "research", "分析"],
    "writing": ["写", "总结", "报告", "上传", "notion", "文章", "文档", "写", "compose", "write", "summary", "report"],
    "planning": ["计划", "规划", "安排", "方案", "plan", "strategy"],
    "analysis": ["分析", "解读", "对比", "评估", "analyze", "analysis", "compare", "evaluate"],
    "automation": ["自动", "定时", "提醒", "cron", "自动化", "schedule", "设置", "auto", "workflow"],
    "information": ["天气", "新闻", "资讯", "信息", "news", "weather", "info", "查询"],
    "conversation": ["聊天", "对话", "问", "help", "chat", "talk"]
}

# Risk indicators
HIGH_RISK_PATTERNS = [
    r"rm\s+-rf", r"delete.*production", r"drop\s+table", 
    r"ALTER.*TABLE.*DROP", r"sudo\s+rm", r"永久删除"
]

MEDIUM_RISK_PATTERNS = [
    r"写.*文件", r"修改.*配置", r"edit.*config", 
    r"update.*database", r"deploy", r"发布"
]

def analyze_task(message: str, context: Optional[Dict] = None) -> Dict:
    """Generate structured task understanding"""
    
    task_id = f"t_{datetime.now().strftime('%Y%m%d')}_{str(uuid.uuid4())[:4]}"
    
    # Detect task type
    task_type = detect_task_type(message)
    
    # Detect scenario
    scenario = detect_scenario(message, task_type)
    
    # Assess complexity
    complexity = assess_complexity(message, context)
    
    # Assess risk
    risk = assess_risk(message)
    
    # Check if file write needed
    file_write = detect_file_write(message)
    
    # Get file scope
    file_scope = extract_file_paths(message) if file_write else None
    
    # Detect required tools
    tools = detect_required_tools(message, task_type)
    
    # Generate subtasks
    subtasks = generate_subtasks(message, task_type, complexity)
    
    # Calculate uncertainty
    uncertainty = calculate_uncertainty(message, context)
    
    # Detect priority
    priority = detect_priority(message, context)
    
    # Generate tags
    tags = generate_tags(message, task_type, scenario)
    
    return {
        "task_id": task_id,
        "parent_task_id": None,
        "task_type": task_type,
        "scenario": scenario,
        "complexity_level": complexity,
        "risk_level": risk,
        "file_write_flag": file_write,
        "file_scope": file_scope,
        "requires_tools": tools,
        "candidate_subtasks": subtasks,
        "uncertainty_level": uncertainty,
        "priority": priority,
        "tags": tags,
        "created_at": datetime.now().isoformat(),
        "raw_message": message[:200]  # Store snippet for context
    }

def detect_task_type(message: str) -> str:
    """Detect primary task type from message"""
    message_lower = message.lower()
    
    for task_type, keywords in TASK_TYPE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in message_lower:
                return task_type
    
    return "conversation"  # Default

def detect_scenario(message: str, task_type: str) -> str:
    """Detect specific scenario"""
    message_lower = message.lower()
    
    # News related
    if any(w in message_lower for w in ["新闻", "news", "资讯", "总结"]):
        return "news_summary"
    
    # Code related
    if any(w in message_lower for w in ["代码", "code", "script", "脚本"]):
        return "code_development"
    
    # Automation
    if any(w in message_lower for w in ["定时", "自动", "cron", "schedule"]):
        return "automation_setup"
    
    # Research
    if any(w in message_lower for w in ["搜索", "找", "查询", "fetch"]):
        return "information_retrieval"
    
    return f"{task_type}_general"

def assess_complexity(message: str, context: Optional[Dict] = None) -> str:
    """Assess task complexity"""
    # Multi-step indicators
    multi_step_words = ["然后", "接下来", "再", "and then", "also", "同时", "此外"]
    
    if any(word in message.lower() for word in multi_step_words):
        return "L1"
    
    # Check for multiple requests
    sentences = re.split(r'[。;,\n]', message)
    if len([s for s in sentences if s.strip()]) > 3:
        return "L2"
    
    return "L0"

def assess_risk(message: str) -> str:
    """Assess risk level"""
    message_lower = message.lower()
    
    for pattern in HIGH_RISK_PATTERNS:
        if re.search(pattern, message_lower):
            return "high"
    
    for pattern in MEDIUM_RISK_PATTERNS:
        if re.search(pattern, message_lower):
            return "medium"
    
    # Check for external actions
    external_actions = ["发送", "发邮件", "发推", "发微博", "send email", "tweet", "post"]
    if any(action in message_lower for action in external_actions):
        return "medium"
    
    return "low"

def detect_file_write(message: str) -> bool:
    """Check if task involves file writes"""
    write_indicators = ["写", "保存", "上传", "创建", "write", "save", "create", "upload", "到文件"]
    return any(indicator in message.lower() for indicator in write_indicators)

def extract_file_paths(message: str) -> List[str]:
    """Extract file paths from message"""
    # Common path patterns
    patterns = [
        r'(?:/|~)?(?:[\w-]+/)*[\w.-]+',  # Unix paths
        r'[A-Z]:\\[\w\\]+',  # Windows paths
    ]
    
    paths = []
    for pattern in patterns:
        matches = re.findall(pattern, message)
        paths.extend(matches)
    
    return list(set(paths))[:5]  # Limit to 5 paths

def detect_required_tools(message: str, task_type: str) -> List[str]:
    """Detect required tools"""
    tools = []
    message_lower = message.lower()
    
    # Web fetch
    if any(w in message_lower for w in ["搜索", "获取", "fetch", "web", "新闻"]):
        tools.append("web_fetch")
    
    # Browser
    if any(w in message_lower for w in ["浏览器", "打开", "browser", "点击"]):
        tools.append("browser")
    
    # File operations
    if any(w in message_lower for w in ["写", "保存", "上传", "write", "save"]):
        tools.append("filesystem")
    
    # Code execution
    if any(w in message_lower for w in ["运行", "执行", "run", "execute"]):
        tools.append("exec")
    
    # Message sending
    if any(w in message_lower for w in ["发送", "发", "send", "通知"]):
        tools.append("message")
    
    # Always include conversation as fallback
    if not tools:
        tools.append("conversation")
    
    return list(set(tools))

def generate_subtasks(message: str, task_type: str, complexity: str) -> List[str]:
    """Generate candidate subtasks"""
    subtasks = []
    
    if task_type == "research":
        subtasks = ["fetch_information", "analyze_data", "summarize_findings"]
    elif task_type == "coding":
        subtasks = ["analyze_requirements", "write_code", "validate_output"]
    elif task_type == "writing":
        subtasks = ["gather_information", "organize_content", "write_output"]
    elif task_type == "automation":
        subtasks = ["design_workflow", "implement_script", "setup_schedule"]
    elif complexity == "L2":
        subtasks = ["break_down_task", "execute_subtasks", "integrate_results"]
    else:
        subtasks = ["execute_primary_action"]
    
    return subtasks

def calculate_uncertainty(message: str, context: Optional[Dict] = None) -> float:
    """Calculate uncertainty level (0=certain, 1=uncertain)"""
    uncertainty = 0.3  # Base uncertainty
    
    # Ambiguous language increases uncertainty
    ambiguous_words = ["可能", "也许", "大概", "perhaps", "maybe", "might", "some"]
    if any(word in message.lower() for word in ambiguous_words):
        uncertainty += 0.2
    
    # Very short messages have higher uncertainty
    if len(message) < 20:
        uncertainty += 0.3
    
    # Clear requests reduce uncertainty
    clear_words = ["要", "需要", "帮我", "请", "need", "want", "please"]
    if any(word in message.lower() for word in clear_words):
        uncertainty -= 0.1
    
    return min(1.0, max(0.0, uncertainty))

def detect_priority(message: str, context: Optional[Dict] = None) -> str:
    """Detect priority level"""
    message_lower = message.lower()
    
    # Urgent indicators
    urgent_words = ["紧急", "马上", "立即", "urgent", "asap", "immediately", "现在"]
    if any(word in message_lower for word in urgent_words):
        return "P0"
    
    # Important indicators
    important_words = ["重要", "关键", "需要", "important", "critical"]
    if any(word in message_lower for word in important_words):
        return "P1"
    
    return "P2"  # Default

def generate_tags(message: str, task_type: str, scenario: str) -> List[str]:
    """Generate task tags"""
    tags = [task_type, scenario]
    
    message_lower = message.lower()
    
    # Domain tags
    if any(w in message_lower for w in ["经济", "金融", "财经", "economy", "finance"]):
        tags.append("finance")
    if any(w in message_lower for w in ["科技", "技术", "tech"]):
        tags.append("tech")
    if any(w in message_lower for w in ["政治", "政治"]):
        tags.append("politics")
    if any(w in message_lower for w in ["中国", "国内"]):
        tags.append("china")
    if any(w in message_lower for w in ["美国", "国外"]):
        tags.append("us")
    
    # Action tags
    if "notion" in message_lower:
        tags.append("notion")
    if "定时" in message_lower or "cron" in message_lower:
        tags.append("scheduled")
    
    return list(set(tags))

if __name__ == "__main__":
    # Test
    test_messages = [
        "帮我搜索今天的新闻总结，上传到Notion",
        "写一个Python脚本自动抓取天气",
        "分析一下当前的经济形势"
    ]
    
    for msg in test_messages:
        result = analyze_task(msg)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        print("---")
