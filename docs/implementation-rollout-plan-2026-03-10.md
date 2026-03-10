# OpenClaw 详细落实计划（Execution Plan v1.1）

> 依据：`SYSTEM_FRAMEWORK_PROPOSAL.md` 第 29–35 节与相关 contract/docs。  
> 版本：v1.1（补充任务连续性、结果评估、记忆生命周期骨架、回归判定冻结）

## 0. 目标与范围

### 0.1 目标

在不破坏现网稳定性的前提下，把“方案”落成“可持续运行系统”：

- 机制门控可执行
- 字段语义一致
- 状态机可审计
- 入口不可绕过
- 文件治理可落地
- 任务连续性可判定
- 成功/失败/部分成功可统一评估
- 记忆生命周期可控
- 回归发布可机器判定

### 0.2 范围

覆盖以下模块：

- Task/Subtask Runtime
- Continuity Resolver
- Outcome Evaluator
- Memory Ingest / Recall / Lifecycle
- Proposal / Governance / Canary / Rollback
- Decision Trace / Metrics
- File Catalog + File Governance

### 0.3 实施原则

- 先冻结契约，再落地执行器
- 先收口入口，再开放能力
- 先保证可回滚，再扩大自动化
- 先让 candidate 运行，再让 active 生效
- 先做低风险 staging，再考虑更高风险路径

---

## 1. 实施总排期（6 周）

| 周次 | 主题 | 核心交付 | 验收标准 |
|---|---|---|---|
| W1 | 契约冻结 | Canonical 字段/对象契约冻结；schema 对齐清单；continuity/outcome 字段入字典 | 所有核心 schema 通过 canonical 校验 |
| W2 | 入口与状态机 | Single Ingress 落地；Continuity Resolver；Task/Proposal/Memory/File 状态机执行器 | 旁路调用被拦截，状态跳跃被拒绝 |
| W3 | 执行门控 | before/execute/after 全链路阈值门控；Outcome Evaluator | done/constraint/validation 三检齐全率 100%，outcome 字段完整率 100% |
| W4 | 记忆与提案 | memory ingest/recall/lifecycle + proposal queue 优先级；promotion/retention skeleton | recall 命中率稳定，proposal 去重合并生效，candidate 不直升 |
| W5 | 文件治理 | file_catalog precheck/enforce + ownership lock + patch tx | 越权写入阻断率 100%，可回滚 |
| W6 | 回归与发布 | golden/dirty/staging 全量验证 + canary 发布 + regression rules 冻结 | 回归报告 pass，关键 SLO 达标 |

---

## 2. 分模块落实清单

### 2.1 Contracts & Schema（W1）

**任务**

1. 冻结 `canonical_field_dictionary` 与 `canonical_object_schema`。
2. 对齐以下 schema：
   - `task_schema.json`
   - `subtask_schema.json`
   - `skill_registry_schema.json`
   - `decision_trace.schema.json`
   - `continuity_resolver.schema.json`
   - `task_outcome.schema.json`
3. 建立“新 schema 不得绕过字典” CI 规则。
4. 将以下字段纳入 canonical 强约束：
   - `task_id / subtask_id / root_task_id / parent_task_id`
   - `continuity_type / task_status / proposal_status / memory_status / file_status`
   - `interaction_success / execution_success / goal_success / governance_success / overall_outcome`
   - `trace_version / schema_version / router_version / policy_version / config_version`

**验收**

- `validate_canonical_alignment.py` 在 CI 必跑且为 PASS。
- 禁用同义字段（`job_type / work_type / risk_level` 混用等）为硬失败。
- continuity / outcome 相关字段全部进入 canonical 字典。

### 2.2 Ingress & State Machine（W2）

**任务**

1. 实现统一 Envelope 入口。
2. 加入 `ingress_guard` 与 `chain_guard`。
3. 落地 `continuity_resolver`：
   - `new_task`
   - `continue_existing_task`
   - `attach_as_subtask`
   - `fork_from_existing_task`
4. 落地四类状态机执行器：
   - task
   - proposal
   - memory
   - file
5. 迁移规则：禁止非法跳跃迁移。
6. 所有进入执行层的请求必须具备：
   - `message_id`
   - `session_id`
   - `ingested_by=evoclaw`
   - `continuity_resolution`

**验收**

- 非 Envelope 请求执行失败。
- 未经过 continuity resolution 的请求不可进入主执行链。
- 非法状态迁移记录拒绝日志并告警。
- 所有主链路对象均可追溯到 `message_id -> task_id -> trace_id`。

### 2.3 Runtime Gates（W3）

**任务**

1. `before_task`：规则版本固定（rule version pinning）。
2. `before_subtask`：局部 scope 与策略校验。
3. `routing`：tie-breaker + abstain gate。
4. `execute`：sandbox + timeout/budget + 三检：
   - done criteria check
   - constraint check
   - validation check
5. `after_task`：cross-subtask consistency check。
6. 落地 Outcome Evaluator：
   - `interaction_success`
   - `execution_success`
   - `goal_success`
   - `governance_success`
   - `overall_outcome = success / partial / failure`

**验收**

- 每个子任务都有完整 audit 字段。
- 三检缺失即 failure，不可标 success。
- outcome 字段完整率 100%。
- `overall_outcome` 与 failure taxonomy 一致，不允许空缺。

### 2.4 Memory / Proposal（W4）

**任务**

1. Memory Ingest：dedup + schema migration guard。
2. Memory Recall：rules > experience > candidate 硬优先级。
3. Proposal Processor：priority queue + similarity merge。
4. Governance Gate：review quorum + freeze window。
5. 建立最小 `promotion_guard`：
   - candidate 不可直升 active
   - episodic / candidate → semantic 必须过阈值与 review
6. 建立最小 retention/archive skeleton：
   - working / buffer 过期
   - recovery notes 归档
   - 旧 candidate 降级或归档
   - append-only event 不可覆盖

**验收**

- 候选对象不可直升 active。
- 重复提案合并率可观测。
- promote / archive 有明确状态与审计记录。
- retention 不得删除审计必要证据。

### 2.5 File Governance（W5）

**任务**

1. 用 `build_file_catalog_db.py` 定时刷新目录库。
2. `catalog_precheck(file_scope)` 前置到 before hooks。
3. `catalog_enforce(path, mode)` 前置到执行器。
4. 核心路径上锁：ownership lock + transactional patch apply。
5. 强制文件分类：
   - CORE
   - CONTROLLED
   - WORKING
   - GENERATED
6. patch-first 机制落地：禁止高风险文件 direct overwrite。

**验收**

- CORE 文件 direct write 0 次。
- 所有失败补丁自动回滚可追溯。
- `file_policy_block_count` 与 `unauthorized_write_attempt_count` 可观测。
- 文件操作必须带 `file_id / writable_mode / policy_version / evidence_hash`。

### 2.6 Regression & Release（W6）

**任务**

1. 执行 golden + dirty + real sample + staging。
2. 生成回归报告和 layered dashboard。
3. canary 发布，观察并回滚演练。
4. 冻结 `regression_rules.yaml v1`：
   - pass
   - warning
   - fail
5. 将 regression 结果纳入发布门：
   - 未达标不得发布
   - warning 级必须人工确认
   - fail 级必须阻断并复盘

**验收**

- 关键 SLO 达标（见第 4 节）。
- 回滚演练成功率 100%。
- `regression_report.json` 自动给出 pass / warning / fail。
- regression 判定规则版本化并进入审计日志。

---

## 3. 里程碑与交付物

| 里程碑 | 截止 | 必交付 |
|---|---|---|
| M1 契约冻结 | W1 末 | 字段字典 v1 + 对象 schema v1 + CI 校验 + continuity/outcome schema |
| M2 主链路闭环 | W3 末 | ingress + continuity + state machine + runtime gates + outcome evaluator |
| M3 治理闭环 | W5 末 | memory/proposal/file governance 全链路 + promotion/retention skeleton |
| M4 发布就绪 | W6 末 | 回归报告 + canary 结果 + 发布建议 + regression rules v1 |

---

## 4. 运行 SLO / KPI

- `ingress_compliance_rate >= 99.9%`
- `bypass_attempt_count = 0`（生产）
- `task_outcome_fields_completeness = 100%`
- `decision_trace_completeness = 100%`
- `state_transition_rejection_logging_rate = 100%`
- `unauthorized_write_attempt_count = 0`（生产）
- `rollback_recovery_time <= 5 min`
- `canonical_alignment_pass_rate = 100%`

---

## 5. 风险与缓解

| 风险 | 表现 | 缓解 |
|---|---|---|
| 字段漂移回潮 | 新表绕过字典 | CI 强制 canonical validator |
| 旁路执行 | 脚本直接写文件或绕过 ingress | ingress_guard + chain_guard + 审计告警 |
| 任务连续性误判 | 多条消息被错误拆分或错误合并 | continuity resolver + confidence threshold + fallback review |
| 结果判定漂移 | success/failure 口径变动 | outcome evaluator 固化 schema + regression 对照 |
| 回归覆盖不足 | canary 后才暴露问题 | 强制 dirty suite + real sample |
| 文件治理误杀 | 合法写被误阻断 | 分级白名单 + review fallback |
| 记忆污染 | candidate 误升 active | promotion guard + review-only 默认策略 |

---

## 6. 执行责任矩阵（RACI 简版）

| 事项 | R | A | C | I |
|---|---|---|---|---|
| 契约与字段标准 | Runtime Maintainer | Governance Owner | DBA/QA | 全员 |
| 入口、连续性与状态机 | Runtime Maintainer | Governance Owner | QA | 全员 |
| Outcome Evaluator 与门控 | Runtime Maintainer | Governance Owner | QA | 全员 |
| 文件治理与目录库 | Platform Owner | Governance Owner | Runtime/QA | 全员 |
| 回归与发布 | QA Lead | Release Owner | Runtime/Governance | 全员 |

---

## 7. 第一周执行清单（可直接开工）

1. 在 CI 加 `python3 evoclaw/validators/validate_canonical_alignment.py`。
2. 补充 Envelope schema 并接入 ingress_router。
3. 增加 state transition validator（task/proposal/memory/file）。
4. 将 `build_file_catalog_db.py` 接入每日定时任务。
5. 产出第一版 `regression_report.json` 基线。
6. 增加 `continuity_resolver.schema.json` 与最小测试。
7. 输出第一版 `canonical_field_dictionary.md` 冻结快照并纳入版本控制。

