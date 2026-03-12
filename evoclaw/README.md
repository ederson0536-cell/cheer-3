# EvoClaw Runtime Framework

> 基于 SYSTEM_FRAMEWORK_PROPOSAL.md 的完整落地实现 (v1.0)
>
> ⚠️ **运行态说明（重要）**：当前工作区已切换为 **DB-first**。`memory/memory.db` 是唯一主读写源；README 中出现的部分目录路径（如
> `memory/tasks/`、`memory/proposals/`）属于早期文件制模型示意，现阶段主要用于
> 历史兼容/迁移说明，而非运行时主通道。

## 概述

本框架实现了一个可持续进化、可协同、可审计的 Agent Runtime 控制系统。

## 目录结构

```
evoclaw/
├── runtime/
│   ├── contracts/                    # 协议 Schema
│   │   ├── task_schema.json
│   │   ├── subtask_schema.json
│   │   ├── skill_registry_schema.json
│   │   ├── failure_taxonomy.json
│   │   └── candidate_memory.json
│   ├── components/                   # 核心组件
│   │   ├── task_engine.py           # 任务理解
│   │   ├── skill_registry.py        # 技能注册
│   │   ├── skill_router.py          # 技能路由
│   │   ├── proposal_processor.py    # 提案处理
│   │   ├── passive_learning.py      # 被动学习
│   │   ├── governance.py            # 治理门
│   │   ├── candidate_memory.py     # 候选记忆
│   │   ├── graph_memory.py         # 图谱记忆
│   │   └── active_learning.py      # 主动学习
│   ├── hooks/                       # 四钩子
│   │   ├── before_task.py
│   │   ├── after_task.py
│   │   ├── before_subtask.py
│   │   └── after_subtask.py
│   ├── task_manager.py
│   ├── enhanced_task_manager.py
│   ├── unified_runtime.py
│   └── evoclaw_runtime.py          # 完整运行时
├── skills_registry/
└── memory/
    ├── working/
    ├── tasks/
    ├── subtasks/
    ├── proposals/
    ├── governance/
    ├── candidate/
    ├── semantic/
    └── graph/
```

## 已实现功能

### 第一阶段 ✅
- [x] 任务理解引擎
- [x] before_task / after_task hooks
- [x] 基础记忆系统
- [x] 任务分类记录

### 第二阶段 ✅
- [x] 子任务 Schema
- [x] 技能注册表 (7个预置技能)
- [x] 技能路由器 (6因素评分)
- [x] before_subtask / after_subtask hooks

### 第三阶段 ✅
- [x] Proposal Processor
- [x] Failure Taxonomy (9种失败分类)
- [x] Passive Learning
- [x] Governance Gate

### 第四阶段 ✅
- [x] **Candidate Memory** - 候选知识生命周期管理
- [x] **Graph Memory** - 图谱关系检索
- [x] **Active Learning** - 主动学习验证
- [x] **EvoClaw Runtime** - 完整统一运行时

---

## 核心组件

### 1. 任务理解引擎
自动识别任务类型、风险、复杂度。

### 2. 技能系统
- 7个预置技能
- 6因素路由评分
- 自动性能追踪

### 3. 学习系统
| 类型 | 功能 |
|------|------|
| Passive Learning | 分析历史数据，识别失败模式 |
| Active Learning | 主动验证候选知识 |
| Graph Memory | 关系图谱检索 |

### 4. 治理系统
- 提案处理
- 审批流程
- Canary 发布

---

## 使用方式

### 完整运行时 (推荐)
```python
from evoclaw.runtime.evoclaw_runtime import EvoClawRuntime

runtime = EvoClawRuntime()

# 任务执行
runtime.start("搜索今天的经济新闻")
runtime.execute_subtask("fetch", "获取数据")
runtime.complete_subtask(result="完成")
runtime.complete(result="完成")

# 学习循环
result = runtime.learn()

# 查看状态
status = runtime.get_status()
```

### CLI 方式
```bash
python evoclaw_runtime.py start "任务"
python evoclaw_runtime.py subtask fetch "获取数据"
python evoclaw_runtime.py finish
python evoclaw_runtime.py learn
python evoclaw_runtime.py status
```

---

## 数据流

```
用户消息
    ↓
任务理解 → 技能路由
    ↓
before_task → before_subtask
    ↓
    执行子任务
    ↓
after_subtask → after_task
    ↓
提案生成 → 被动学习 → 候选记忆
    ↓
主动学习 → 验证 → 晋升语义记忆
    ↓
图谱更新 → 关系检索
```

---

## 记忆系统（DB-first，已更新）

### 当前主路径

| 层级 | 主路径 | 说明 |
|------|--------|------|
| Canonical Store | `memory/memory.db` | 运行态唯一主读写源 |
| Experience API | `experiences` (SQL VIEW) | 兼容入口，底层映射 `memories` |
| Core Tables | `memories / proposals / reflections / task_runs / graph_entities / graph_relations / soul_history / system_state` | 统一结构化存储 |

### 兼容目录（非主通道）

以下目录概念保留用于历史文档、迁移脚本或离线归档，不作为运行时主写入目标：

- `memory/working/`
- `memory/tasks/`
- `memory/subtasks/`
- `memory/proposals/`
- `memory/governance/`
- `memory/candidate/`
- `memory/semantic/`
- `memory/graph/`

如需核查当前运行状态，请优先检查 `memory/memory.db` 与 `evoclaw/sqlite_memory.py`。

---

## 提案流程

```
执行反馈 → 聚类分析 → 生成提案 → 审批(canary) → 发布/回滚
```

---

## 成功指标

- 任务成功率
- 技能路由准确率
- 提案转化率
- 候选知识晋升率

---

*基于 SYSTEM_FRAMEWORK_PROPOSAL.md v3 实现 | Version 1.0*
