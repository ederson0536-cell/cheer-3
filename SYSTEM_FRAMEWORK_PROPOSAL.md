# OpenClaw 最终系统框架方案（v3）

> 目标：构建一个可持续进化、可协同、可审计、可回滚的 Agent Runtime。
> 核心目标不再是“堆叠更多技能”，而是建立一套能够稳定管理技能、规则、经验和进化流程的系统控制面。
> 重点解决：**执行效率 + 记忆命中 + 技能匹配 + 安全演进**。

---

# 1. 设计总纲：从“四层一闭环”升级为“控制面 + 数据面 + 四钩子 + 发布门”

## 1.1 核心原则

本系统不再将技能视为并列能力集合，而是将其纳入统一控制框架中管理。

系统分为两大部分：

- **控制面（Control Plane）**：负责理解任务、注入规则、分解任务、匹配技能、审核提案、控制发布。
- **数据面（Data Plane）**：负责承载记忆、日志、规则、经验、候选知识、技能统计与关系图谱。

同时引入四个执行钩子：

- `before_task`
- `before_subtask`
- `after_subtask`
- `after_task`

并加入一个强约束治理门：

- **Governance Gate**

---

# 2. 总体架构

## 2.1 控制面（Control Plane）

控制面由以下组件组成：

- **Task Understanding Engine**
  - 负责解析用户输入，输出结构化任务理解结果。
- **Rule Injection Engine**
  - 根据任务类型、风险级别、文件操作范围注入规则。
- **Planner / Decomposer**
  - 负责任务分解、依赖建模、复杂度分层。
- **Skill Router**
  - 基于硬约束、规则一致性、历史表现、成本进行技能匹配。
- **Proposal Processor**
  - 消费执行反馈并生成可验证候选变更。
- **Governance Gate**
  - 审批高风险改动、技能上线、规则发布与回滚。

## 2.2 数据面（Data Plane）

数据面由以下存储层组成：

- **Working Memory**
- **Working Buffer**
- **Decision WAL**
- **Recovery Notes**
- **Episodic Memory**
- **Semantic Memory**
- **Candidate Memory**
- **Skill Registry**
- **Skill Performance Store**
- **Graph Memory**

---

# 3. 统一闭环：三条闭环并行协作

## 3.1 总任务闭环

`Recall → Plan → Execute → Summarize → Propose → Evolve → Validate`

用于保证任务层面的全局方向正确。

## 3.2 子任务闭环

`Recall_subtask → Route_subtask → Execute_subtask → Review_subtask → Log_subtask`

用于保证局部决策精细化，不把总任务经验错误泛化到所有子任务。

## 3.3 提案发布闭环

`Collect → Cluster → Candidate Generate → Review → Canary → Publish / Rollback`

用于保证整改与演进可控、可审计、可回滚。

---

# 4. 执行 Runtime：从消息进入到任务结束

## 4.1 每条消息的标准流程

1. 接收消息
2. 任务理解
3. `before_task`
4. 任务分解
5. 对每个子任务执行：
   - `before_subtask`
   - 子任务技能路由
   - 子任务执行
   - `after_subtask`
6. 汇总所有子任务结果
7. `after_task`
8. 反馈入记忆与提案队列

## 4.2 执行层关键原则

- **规则先行**
- **经验按粒度检索**
- **技能选择必须可解释**
- **失败必须可恢复**
- **候选知识不能直接污染在线执行**
- **高风险写操作必须经过治理门约束**

---

# 5. 任务理解（Task Understanding Engine）

## 5.1 任务理解输出 Schema

每次任务进入后，必须先生成结构化理解结果。

### 字段定义（类型 + 必填性）

- `task_id`: `string`（必填）
- `parent_task_id`: `string | null`（选填，根任务可为 `null`）
- `task_type`: `enum<string>`（必填，如 `coding` / `research` / `planning`）
- `scenario`: `string`（必填）
- `complexity_level`: `enum<string>`（必填，`L0 | L1 | L2`）
- `risk_level`: `enum<string>`（必填，`low | medium | high`）
- `file_write_flag`: `boolean`（必填）
- `file_scope`: `array<string>`（当 `file_write_flag=true` 时必填）
- `requires_tools`: `array<string>`（必填，可为空数组）
- `candidate_subtasks`: `array<string>`（必填，可为空数组）
- `uncertainty_level`: `number`（必填，范围 `0.0 ~ 1.0`）

### 最小 JSON 示例

```json
{
  "task_id": "t_001",
  "parent_task_id": null,
  "task_type": "coding",
  "scenario": "modify_existing_file",
  "complexity_level": "L1",
  "risk_level": "medium",
  "file_write_flag": true,
  "file_scope": ["src/api"],
  "requires_tools": ["filesystem", "search"],
  "candidate_subtasks": ["analyze_code", "edit_file", "run_check"],
  "uncertainty_level": 0.22
}
```

## 5.2 复杂度分层

- **L0**：单步任务
- **L1**：2~4 步串行任务
- **L2**：多子任务并行/依赖任务

复杂度决定是否必须启用 Subtask Loop。

---

# 6. 任务分解与子任务建模

## 6.1 子任务统一结构

每个子任务必须使用统一结构，避免不同执行器“各自脑补字段”。

### 字段定义（类型 + 必填性）

- `subtask_id`: `string`（必填）
- `parent_task_id`: `string`（必填）
- `subtask_type`: `enum<string>`（必填，如 `analyze` / `edit_file` / `run_validation`）
- `goal`: `string`（必填）
- `local_scenario`: `string`（必填）
- `required_tools`: `array<string>`（必填，可为空数组）
- `required_skill`: `string`（选填，未指定时由 Router 决定）
- `constraints`: `array<string>`（必填，可为空数组）
- `file_scope`: `array<string>`（涉及文件读写时必填）
- `done_criteria`: `array<string>`（必填，至少 1 条）

### 最小 JSON 示例

```json
{
  "subtask_id": "st_001",
  "parent_task_id": "t_001",
  "subtask_type": "edit_file",
  "goal": "modify API handler logic",
  "local_scenario": "update_existing_module",
  "required_tools": ["filesystem", "search"],
  "required_skill": "coding_editor",
  "constraints": ["no_cross_directory_write"],
  "file_scope": ["src/api/handler.ts"],
  "done_criteria": ["build passes", "diff reviewed"]
}
```

## 6.2 子任务分解原则

- 子任务粒度必须足够支持精准规则注入
- 复杂任务必须显式标出依赖关系
- 不允许在未分解清楚时直接做高风险写操作
- 子任务可覆盖父任务低优先策略，但不可覆盖强规则

---

# 7. 四钩子机制（Hooks）

## 7.1 before_task

### 输入
- `task_type`
- `scenario`
- `risk_level`
- `file_write_flag`
- `file_scope`

### 动作
- 注入通用 guardrails
- 注入任务类型规则
- 注入风险级规则
- 做任务级粗检索
- 生成初始规划护栏

### 输出
- `task_guardrail_bundle`
- `task_checklist`
- `task_level_recall_packet`

## 7.2 before_subtask

### 输入
- `subtask_type`
- `local_scenario`
- `tool_need`
- `file_scope`
- `risk_level`

### 动作
- 拉取子任务强规则
- 拉取局部场景经验
- 拉取候选技能列表
- 生成局部执行检查清单
- 在文件操作子任务中强制注入路径/作用域校验

### 输出
- `subtask_guardrail_bundle`
- `subtask_recommended_skills`
- `local_checklist`

## 7.3 after_subtask

### 必须记录
- 选择了哪个技能
- 为什么选择
- 是否成功
- 耗时
- 是否返工
- 失败模式
- 是否需要人审
- 是否生成局部提案

### 作用
- 为技能路由提供子任务级反馈
- 为 Proposal Processor 提供高分辨率样本
- 为失败归因提供结构化证据

## 7.4 after_task

### 输入
- 执行轨迹
- 所有子任务结果
- 错误信息
- 用户反馈

### 动作
- 生成总任务总结
- 聚合子任务层反馈
- 提取跨子任务模式
- 产出结构化提案
- 更新 episodic memory
- 判断是否可晋升 semantic memory

### 输出
- `task_summary`
- `feedback_packet`
- `proposal_queue_item`

---

# 8. 规则系统（Rule System）

## 8.1 规则优先级

系统必须定义规则优先级，解决冲突时“听谁的”：

- **P0: Hard Rules**
  - 不可覆盖
  - 如安全边界、权限边界、文件作用域约束
- **P1: Governance Rules**
  - 默认不可覆盖
  - 如审批、回滚、上线策略
- **P2: Task-Type Rules**
  - 按任务类型适用
- **P3: Scenario Experience Rules**
  - 按局部场景适用
- **P4: Candidate Suggestions**
  - 仅建议，不强制

## 8.2 规则冲突处理

规则冲突时按优先级裁决：

1. P0 优先于一切
2. P1 只能在治理授权下变更
3. P3 可覆盖 P2 的低优先部分
4. P4 永远不能覆盖正式规则

---

# 9. 双轨记忆检索（Memory Retrieval）

## 9.1 检索必须分为两条轨道

不能把规则、经验、候选知识全部混在一个 recall 流程中。

### 轨道 A：规则检索
检索目标：

- hard rules
- governance rules
- task-type rules
- scenario rules

主键：

- `task_type`
- `subtask_type`
- `risk_level`
- `file_scope`

### 轨道 B：经验检索
检索目标：

- 相似成功经验
- 相似失败模式
- 技能路由历史
- 近期有效路径

主键：

- `local_scenario`
- `similar_failure_mode`
- `prior_skill_outcomes`
- `recent_successful_traces`

## 9.2 召回融合原则

- 规则先于经验
- 经验先于候选知识
- 候选知识只作为建议
- 技能路由必须同时参考规则检索与经验检索结果

---

# 10. 记忆系统（Memory Plane）

## 10.1 记忆分层

- **Working Memory**
  - 当前消息/当前任务临时上下文
- **Working Buffer**
  - 当前阶段高频中间结论与待办
- **Decision WAL**
  - 关键决策及理由的追加式记录
- **Recovery Notes**
  - 中断恢复说明
- **Episodic Memory**
  - 任务过程日志
- **Semantic Memory**
  - 稳定规则与复用经验
- **Candidate Memory**
  - 待验证知识
- **Graph Memory**
  - 类型化关系图

## 10.2 Proactive Buffer 机制

### Decision WAL
- 记录关键决策与理由
- 不允许就地覆盖
- 便于回放与复盘

### Working Buffer
- 保存当前阶段最常用的中间结论
- 仅为短期缓存
- 不直接作为长期规则来源

### Recovery Notes
- 记录“做到哪里、下一步是什么、为什么这样做”
- 用于中断恢复与 after_task 汇总

## 10.3 晋升与归档原则

- Episodic 中高频稳定模式可晋升 Semantic
- Candidate 验证通过后方可晋升 Semantic
- Recovery Notes 在任务关闭后归档
- Working Buffer 默认不进入长期规则

### 最小晋升阈值（建议默认值）

以下条件建议同时满足，才允许 `Episodic/Candidate -> Semantic`：

1. 连续 `N >= 3` 次相似场景验证有效
2. 未触发高风险冲突（特别是 `P0/P1`）
3. 未违反硬规则与治理规则
4. 返工率低于阈值（建议 `< 15%`）
5. 通过 Governance Gate 的 review（至少 `canary-only`）

若任一条件不满足：

- 保持在 `Candidate/Episodic` 层，不晋升
- 标记 `needs_more_evidence=true`
- 下轮验证优先采样相似场景

---

# 11. 技能系统：从“技能集合”改为“技能注册表”

## 11.1 Skill Registry

每个技能必须注册为标准对象，而不是作为散乱目录存在。

## 11.2 Skill Metadata Schema

### 字段定义（类型 + 必填性）

- `skill_id`: `string`（必填，唯一）
- `skill_name`: `string`（必填）
- `domain`: `string`（必填）
- `supported_task_types`: `array<string>`（必填）
- `supported_subtask_types`: `array<string>`（必填）
- `supported_scenarios`: `array<string>`（选填）
- `required_tools`: `array<string>`（必填）
- `writable_scope`: `array<string>`（选填）
- `risk_profile`: `enum<string>`（必填，`low | medium | high | critical`）
- `compatible_rules`: `array<string>`（选填）
- `incompatible_rules`: `array<string>`（选填）
- `trust_level`: `enum<string>`（必填，`unverified | low | medium | high`）

### 最小 JSON 示例

```json
{
  "skill_id": "coding_editor_v1",
  "skill_name": "Coding Editor",
  "domain": "engineering",
  "supported_task_types": ["coding"],
  "supported_subtask_types": ["edit_file", "run_validation"],
  "supported_scenarios": ["update_existing_module"],
  "required_tools": ["filesystem", "search"],
  "writable_scope": ["src/**"],
  "risk_profile": "medium",
  "compatible_rules": ["rule_safe_edit"],
  "incompatible_rules": ["rule_no_write"],
  "trust_level": "medium"
}
```

## 11.3 Skill Performance Store

每个技能必须持续记录运行表现：

- `avg_success_rate`
- `avg_latency`
- `avg_rework_rate`
- `last_50_outcomes`
- `common_failure_modes`
- `preferred_scenarios`

---

# 12. 技能路由（Skill Router）

## 12.1 路由顺序

按以下顺序筛选与打分：

1. **硬约束匹配**
   - 任务类型
   - 工具权限
   - 文件作用域
2. **规则一致性**
   - 是否符合当前 guardrail bundle
3. **历史表现**
   - 成功率
   - 耗时
   - 返工率
4. **组合收益**
   - 单技能 vs 多技能编排收益
5. **信任等级**
   - 未审计或低信任技能不得参与高风险任务

## 12.2 最小路由评分公式（实现指引）

在通过硬约束过滤后，建议使用以下伪公式计算 `routing_score`：

```text
routing_score =
  hard_constraint_pass
  * (
      w1 * rule_alignment
    + w2 * success_rate
    - w3 * rework_rate
    - w4 * latency_penalty
    + w5 * trust_level
    + w6 * scenario_match
    )
```

说明：

- `hard_constraint_pass`：硬约束通过为 `1`，否则为 `0`
- 所有子分值建议归一化到 `0~1`
- 默认权重建议：`w1=0.20, w2=0.25, w3=0.15, w4=0.10, w5=0.15, w6=0.15`
- `routing_score` 建议阈值：
  - `> 0.75`：可自动执行
  - `0.60~0.75`：进入审慎模式（优先 canary / 人审）
  - `< 0.60`：不建议自动执行

## 12.3 路由必须写回记忆

必须记录：

- 本次为何选中该技能
- 候选技能为何落选
- 实际结果如何
- 下次是否应调整默认策略

---

# 13. 失败分型（Failure Taxonomy）

Proposal Processor 不应处理模糊失败，必须基于结构化失败类型。

## 13.1 标准失败分类

- `understanding_error`
- `routing_error`
- `tool_error`
- `memory_miss`
- `rule_conflict`
- `execution_timeout`
- `file_scope_error`
- `hallucinated_assumption`
- `incomplete_validation`

## 13.2 作用

- 支持高质量聚类
- 支持准确归因
- 支持区分是 recall 问题、routing 问题、tool 问题还是规则问题

---

# 14. Proposal Processor（进化入口）

## 14.1 输入来源

- `after_task`
- `after_subtask`

## 14.2 处理流程

1. 收集提案
2. 聚类相似问题
3. 识别高频失败模式
4. 生成候选变更：
   - `rule_update_candidate`
   - `routing_weight_update_candidate`
   - `memory_policy_update_candidate`

## 14.3 两段式处理

### Stage A: Analyzer
- 只负责分析与生成候选
- 不允许直接修改在线系统

### Stage B: Publisher
- 负责 review
- canary
- publish / rollback

---

# 15. 进化层（Evolution Plane）

## 15.1 被动学习（整改引擎）

来源：高置信度执行反馈与高频失败模式

流程：

1. 提案去重与聚类
2. 风险/收益评估
3. 候选整改生成
4. 小流量验证
5. 生效或回滚

## 15.2 主动学习（探索引擎）

来源：外部信息、新模式、低置信度经验

流程：

1. 生成 `KnowledgeCandidate`
2. 定义验证条件
3. 在后续相关任务中验证
4. 达标后晋升，否则降权或归档

## 15.3 进化层原则

- 只处理候选策略
- 不直接污染在线执行
- 所有改动必须可追踪、可回滚、可审计

---

# 16. 图谱系统（Graph Memory）

## 16.1 实体

- `TaskType`
- `SubtaskType`
- `Scenario`
- `Rule`
- `Skill`
- `Experience`
- `Proposal`
- `KnowledgeCandidate`
- `FailureMode`

## 16.2 关系

- `TaskType -> requires -> Rule`
- `SubtaskType -> prefers -> Skill`
- `Scenario -> triggers -> Rule`
- `Skill -> solved -> Experience`
- `Experience -> improves -> Rule`
- `Proposal -> modifies -> Rule`
- `Proposal -> modifies -> SkillPolicy`
- `KnowledgeCandidate -> validates_against -> Experience`
- `FailureMode -> suggests -> Proposal`

## 16.3 使用原则

- 图谱优先服务检索与解释
- 前期可用关系表/轻图方案，不强依赖重型图数据库
- 不要求一开始图谱全量上线

---

# 17. 治理层（Governance Plane）

## 17.1 Governance Gate

治理门负责：

- 新技能安装审批
- 技能信任等级管理
- 文件写权限约束
- 规则发布审批
- canary 发布
- rollback
- 高风险任务人工确认

## 17.2 禁止事项

- 禁止低信任技能直接执行高风险写操作
- 禁止 Proposal Processor 直接在线改核心执行逻辑
- 禁止 Candidate Knowledge 直接进入 Semantic Memory
- 禁止未审批技能参与生产路径

---

# 18. 最小落地方案（MVP）

## 第 1 阶段
- 上线 `before_task / after_task`
- 建立 Task Understanding Schema
- 建立 Rule Priority
- 建立基础 Semantic / Episodic Memory
- 实现规则检索与经验检索分轨

## 第 2 阶段
- 上线 `before_subtask / after_subtask`
- 建立 Skill Registry
- 建立 Skill Performance Store
- 实现子任务级技能路由评分

## 第 3 阶段
- 上线 Proposal Processor
- 建立 Failure Taxonomy
- 接入被动学习
- 建立 Governance Gate 的 review + canary + rollback

## 第 4 阶段
- 建立 Candidate Memory 验证闭环
- 引入轻量图谱关系检索
- 上线主动学习验证机制
- 逐步完善发布治理与审计看板

---

# 19. 成功指标（Success Metrics）

- 同类任务成功率持续上升
- 子任务级路由准确率上升
- 重复错误率下降
- 规则命中后失败率下降
- 技能平均返工率下降
- 平均任务完成时长下降
- Candidate 转正率稳定提升
- 高风险改动的回滚率可控
- 新技能接入后系统稳定性不下降

---

# 20. 一句话总结

v3 的核心，不再是“拥有更多技能”，而是：

**建立一个能够理解任务、分层检索记忆、在子任务粒度匹配技能、将经验安全演化并通过治理门发布的 Agent Runtime。**

---

# 21. 文件管理与存储治理

本节定义运行期对象如何分层存储、如何命名、如何隔离“候选态与正式态”，避免日志、规则、技能代码互相污染。

## 21.1 存储对象分类

建议按对象语义拆分为四类：

- **Runtime Objects**
  - 任务与子任务执行态数据（working buffer、WAL、recovery notes、临时路由结果）
- **Knowledge Objects**
  - 经验、规则、候选知识、语义记忆、失败分型样本
- **Skill Objects**
  - 技能代码、技能元数据、技能表现统计、技能信任等级
- **Governance Objects**
  - 审批记录、发布单、canary 报告、回滚记录、审计证据

## 21.2 目录与命名规则

建议采用“正式态/候选态分离 + 职责隔离”的目录规范：

- 正式态与候选态分离
  - `memory/semantic/`（正式） vs `memory/candidate/`（候选）
  - `rules/active/`（正式） vs `rules/candidate/`（待发布）
- 技能代码与技能治理信息分离
  - `skills/<skill_id>/`（代码）
  - `governance/skills/<skill_id>/`（信任等级、审批、发布历史）
- 原始日志与正式规则分离
  - `logs/runtime/`（原始执行日志）
  - `rules/active/`（可执行规则）

命名建议：

- 对象 ID：`<domain>_<type>_<date>_<seq>`（如 `rt_task_20260306_001`）
- 候选变更：`cand_<object>_<id>`
- 发布批次：`release_<yyyymmdd>_<seq>`
- 回滚批次：`rollback_<yyyymmdd>_<seq>`

## 21.3 生命周期规则

所有核心对象建议遵循统一生命周期：

1. **创建（create）**
2. **追加（append）**
3. **晋升（promote）**
4. **发布（publish）**
5. **废弃（deprecate）**
6. **归档（archive）**
7. **回滚（rollback）**

治理约束：

- append-only 日志对象不允许覆盖式写入
- promote/publish 必须关联审批记录
- deprecate/archive 必须保留可追溯索引
- rollback 必须引用具体 release 批次

---

# 22. 经验与技能变更管理

本节定义经验和技能的标准变更动作，避免“随手改、不可追踪、不可回滚”。

## 22.1 经验变更动作

经验对象（Episodic/Semantic/Candidate）仅允许以下动作：

- `append`
- `promote`
- `deprecate`
- `archive`

建议规则：

- append 不需要发布，但需带来源与置信度
- promote 必须满足晋升阈值与 review
- deprecate 不等于删除，应保留引用关系
- archive 后默认不参与在线召回，仅在审计/回放使用

## 22.2 技能变更动作

技能对象仅允许以下动作：

- `code_update`
- `metadata_update`
- `routing_policy_update`
- `trust_level_update`

建议规则：

- `code_update` 必须关联测试与变更说明
- `metadata_update` 需要保持与 Skill Registry 一致
- `routing_policy_update` 必须经过 canary 验证
- `trust_level_update` 必须经过 Governance Gate 审批

## 22.3 权限与审批

建议明确三类执行主体与写权限边界：

- **Runtime 可写**
  - working buffer、WAL、episodic 追加日志、子任务执行记录
  - 不可直接写 active rules / semantic promote
- **Processor 可写**
  - proposal_queue、candidate objects、聚类与候选变更包
  - 不可直接发布到正式态
- **Publisher 可发**
  - 仅可发布“已通过 review/canary”的候选包到 active 状态
  - 发布必须写入 release 记录
- **Governance 必审**
  - 高风险写操作
  - P0/P1 相关规则变更
  - Candidate -> Semantic 晋升
  - 低信任技能上生产
  - trust_level 变更


---

# 23. 控制阈值与人工介入策略

本节用于把“可控执行”从原则落到可运行参数。所有阈值建议先以配置项落地（可按环境分别设置 dev/staging/prod），并纳入审计日志。

## 23.1 自动执行阈值

满足以下条件时，允许系统自动执行（无需人工介入）：

- `uncertainty_level < 0.3`
- `routing_score > 0.75`
- 无 `P0/P1` 规则冲突
- 当前任务不包含高风险写操作
- 选中技能 `trust_level >= medium`

建议：

- 阈值不写死在代码中，应由治理层配置中心下发。
- 对不同任务类型可设置不同阈值（例如 coding 与 planning 分开配置）。
- 子任务级别可用更严格阈值（特别是文件写入与规则变更类子任务）。

## 23.2 必须人工审核的条件

出现任一条件即进入人工审核流程（Governance Gate）：

- 高风险写操作（如跨目录批量写、规则库改写、核心配置改动）
- 低信任技能参与执行（`trust_level = low` 或未审计）
- `Candidate Knowledge` 晋升为 `Semantic Memory`
- 规则冲突未解（尤其涉及 `P0/P1`）
- 路由分数接近边界且不确定性偏高（例如 `routing_score <= 0.75` 且 `uncertainty_level >= 0.3`）
- 提案涉及核心执行路径（hook 顺序、规则优先级、发布策略）

审核输出至少包含：

- 审核结论（approve / reject / canary-only）
- 生效范围（任务类型、场景、技能）
- 回滚预案与观察指标

## 23.2.1 人工介入点清单（执行清单）

以下场景必须触发人工介入（可直接作为 Gate checklist）：

- 高风险写文件/批量改写
- 新 skill 首次进入生产路径
- `routing_score` 低于自动阈值
- 多个高优先规则冲突（`P0/P1`）
- `Candidate` 准备晋升 `Semantic`
- Proposal 涉及 `P0/P1` 相关策略改动

## 23.3 自动回滚触发条件

以下信号任一触发时，应自动进入 rollback 流程（优先回滚最新变更包）：

- canary 失败率超过阈值（例如 `fail_rate > baseline + 15%`）
- 返工率显著上升（例如连续窗口超过基线 `20%`）
- 重复错误率升高（同失败模式短时重复出现）
- 高风险任务成功率异常下滑
- 新规则命中后反而导致失败率上升

回滚后必须自动执行：

1. 冻结对应候选发布
2. 记录 `rollback_reason` 与影响范围
3. 触发 Proposal Processor 复盘（重新聚类与归因）
4. 将相关候选降级为 review-only，禁止立即再次发布


---

# 24. 配置中心（Configuration Control）

为避免阈值、权重、发布策略散落在代码中，系统必须提供统一配置中心，作为治理层的参数控制入口。

## 24.1 统一管理范围

配置中心至少统一管理以下参数：

- routing 权重（如 `w1~w6`）
- 自动执行阈值（`routing_score` / `uncertainty_level`）
- canary 阈值（失败率、样本窗口、观察时长）
- rollback 阈值（失败率/返工率/重复错误率）
- 环境差异配置（`dev` / `staging` / `prod`）

## 24.2 配置生效与审计

- 配置变更必须版本化（`config_version`）
- 高风险配置（P0/P1 相关）必须经过 Governance Gate 审批
- 每次运行需记录实际生效配置快照，便于复盘与回滚

## 24.3 最小配置示例

```json
{
  "environment": "staging",
  "routing_weights": {"w1": 0.2, "w2": 0.25, "w3": 0.15, "w4": 0.1, "w5": 0.15, "w6": 0.15},
  "auto_execute_thresholds": {"routing_score_min": 0.75, "uncertainty_max": 0.3},
  "canary_thresholds": {"max_fail_rate_delta": 0.15, "min_sample_size": 50},
  "rollback_thresholds": {"rework_rate_delta": 0.2, "repeat_error_rate_delta": 0.1},
  "config_version": "cfg_20260306_001"
}
```

---

# 25. 已落地的首批实现件（Repository Paths）

- Task/Subtask Contract: `evoclaw/runtime/contracts/task_subtask.schema.json`
- Skill Registry Contract: `evoclaw/runtime/contracts/skill_registry.schema.json`
- Routing Score Reference: `evoclaw/runtime/routing_score.py`
- Memory Write/Read Contract: `evoclaw/runtime/contracts/memory_contract.yaml`
- Proposal Pipeline Contract: `evoclaw/runtime/contracts/proposal_pipeline.schema.json`
- Contract Examples: `evoclaw/runtime/examples/`
- Contract Validator: `evoclaw/validators/validate_runtime_contracts.py`

---

# 26. 运行闭环测试（Executable Loops）

为避免“分段成立但全链路不通”，实现阶段必须执行三类闭环测试：

1. 单任务闭环（Task Input -> before_task -> recall -> route -> episodic -> proposal）
2. 子任务闭环（before_subtask -> route -> after_subtask 高分辨率样本）
3. 提案发布闭环（proposal -> review -> canary -> publish -> rollback）

参考脚本：`evoclaw/validators/test_runtime_loops.py`

补充要求：
- 必须包含 failure injection（`memory_miss` / `routing_error` / `tool_error` / `rule_conflict` / `file_scope_error`）
- 必须输出 baseline metrics（task/subtask success、auto_execute 占比、canary 通过率、rollback 触发率、top failure modes、rework rate）
- decision trace 必须携带版本字段（`trace_version` / `schema_version` / `router_version` / `policy_version`）
- 必须至少跑一个真实样本包（非 purely synthetic）

---

# 27. 回归稳定性机制（Golden Set + Layered Dashboard + Failure Expectations）

- 必须维护固定黄金样本集（至少 5 类）：安全写文件、普通 coding 修改、research/planning、多子任务依赖、高风险回滚。
- 每次修改以下任意项都必须跑黄金样本回归：schema、router 权重、proposal policy、governance 阈值。
- baseline 必须固定口径：`baseline_window` + `sample_scope` + `environment`（dev/staging/prod）。
- 必须维护 failure injection 预期行为表，避免测试只验证“没报错”。
- 分层看板必须至少覆盖：
  - 执行层：task/subtask success、rework
  - 路由层：auto_execute 占比、分数分布、near-threshold
  - 进化层：proposal 生成率、canary 通过率、rollback 率
  - 记忆层：recall hit、memory_miss 占比、candidate promote 率

---

# 28. 稳定化推进优先级（Dirty Inputs / Regression Report / Staging / Service Boundary）

- 必须维护脏输入回归集（dirty suite），用于验证模糊输入与异常输入的鲁棒性。
- 必须生成 `regression_report.json`，并输出 `pass / warning / fail` 结论。
- baseline 必须支持分环境、分窗口比较（至少 `rolling_7d` 与 `rolling_30d`）。
- 必须提供 staging 试运行入口，先覆盖 2~3 类低风险任务。
- 即使不做完整持久服务，也必须先定义服务边界：调度入口、状态存储、trace 落盘、proposal review 队列。
