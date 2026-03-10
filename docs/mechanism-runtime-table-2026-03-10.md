# OpenClaw 机制运行表（优化版）

> 目标：把当前方案从“有模块”提升为“节点有机制、机制有阈值、阈值有处置、处置可审计”。

## 一、当前方案优化要点（先改正，再增强）

1. **从组件描述升级到运行约束**：每个节点都必须绑定 Contract/Policy/Threshold，而不是仅有功能说明。
2. **把成功判定前移到执行阶段**：执行后必须同时满足 done criteria + constraint check + validation check。
3. **candidate 全链路降权**：candidate 仅可建议，不可直接覆盖 active rule/active policy。
4. **高风险默认 review-only**：risk=high 时禁止 auto publish，必须走 governance gate。
5. **补齐 rollback 触发器**：出现 P0/P1 违规、canary 失败、回归指标下穿时自动进入 rollback。

---

## 二、机制运行表（Flow × Node × Mechanism）

| 阶段 | Node | 输入 | 机制（Mechanism） | 阈值/决策门 | 输出 | 失败处置 | 审计字段 |
|---|---|---|---|---|---|---|---|
| 1 | Message Ingress | user message, context | Continuity Resolver + Task Understanding Contract + Input Validator | `valid_schema=true` 才可入队 | task object | schema fail → reject + clarify | `task_id, root_task_id, schema_version` |
| 2 | before_task | task type/scenario/risk | Rule Retrieval + Experience Retrieval + Recall Policy + Guardrail Builder | 规则冲突时 hard rule 优先 | task guardrail/checklist/recall packet | rule conflict → escalate | `rule_set_id, recall_sources` |
| 3 | Decomposer | task object | Subtask Contract + Decomposition Policy + L0/L1/L2 complexity gate | `L2` 强制 subtask loop | subtask list + deps | decomposition fail → fallback planner | `plan_version, complexity_level` |
| 4 | before_subtask | local scenario/tools/scope | Subtask Recall + Local Rule Match + Skill Candidate Filter | file task 必须 scope check | local checklist + candidate skills | scope mismatch → block exec | `subtask_id, scope_hash` |
| 5 | Skill Routing | candidates + constraints | Skill Registry + Routing Score + Trust Filter + Routing Threshold | `score>=T_auto` auto; `T_review<=score<T_auto` review | selected skill + rationale | below threshold → reject/replan | `skill_id, routing_score, threshold` |
| 6 | Execute | skill + checklist | Done Criteria + Constraint Check + Validation Check + High-risk Guard | 三检全过才 success | execution result + trace | any fail → mark fail + rework | `tool_calls, validation_result` |
| 7 | after_subtask | execution trace | Feedback Packet + Failure Taxonomy + Local Reflection + Seed Generator | failure 必须分类 | episodic/failure/seed | unknown failure → taxonomy fallback | `failure_code, rework_count` |
| 8 | after_task | subtask summaries | Outcome Evaluator + Task Summary + Reflection Extractor + Proposal Writer | governance violation=0 才可 closed | task summary + proposal item | violation → reopen + review | `task_outcome, governance_flags` |
| 9 | Memory Ingest | task/subtask artifacts | Write Policy + Object Classification + Append-only Rule | raw event 仅 append | tiered memory objects | classify fail → quarantine | `memory_tier, object_type` |
| 10 | Memory Recall | new task + memory index | Recall Policy + Continuity Resolver + Candidate Filter | `rules > experience > candidate` | recall packet | low confidence → hint only | `recall_confidence, evidence_ids` |
| 11 | Proposal Processor | feedback/failure cluster | Failure Clustering + Candidate Generator + Evidence Aggregator | evidence 不足不可提审 | candidate update | weak evidence → hold | `proposal_id, evidence_count` |
| 12 | Governance Gate | candidate/rule/policy change | Review Policy + Canary Policy + Release Gate + Rollback Trigger | high-risk 仅 review-only | publish/canary/rollback decision | canary fail → rollback | `reviewer, release_version` |
| 13 | Memory Lifecycle | promoted/old objects | Promote/Retention/Archive/Forget Policy + Evidence Threshold | threshold 达标才 promote | active/archived/deprecated | drift detected → demote | `promote_score, retention_ttl` |
| 14 | File Governance | patch/change scope | File Classification + Permission Policy + Patch-first + Versioned Governance | CORE file 禁止 direct write | reviewed patch set | policy breach → hard block | `file_class, diff_hash, policy_id` |

---

## 三、最小运行SLA（建议）

- 路由可解释率 ≥ 99%（每次 routing 都有 score + reason）
- 任务成功判定完整率 = 100%（三检字段必须齐全）
- canary 失败回滚时延 ≤ 5 分钟
- memory promote 误晋升率 ≤ 1%
- 高风险任务绕过 review 次数 = 0

## 四、落地顺序（两周版）

1. **第1周**：先把 14 节点审计字段打齐（trace 完整性优先）。
2. **第2周**：上阈值门控（routing threshold / evidence threshold / rollback trigger）。
3. **并行**：每次版本发布附 `regression_report.json` 与 `decision_trace` 样本。

---

## 五、流程复盘后的缺口与补充机制（本次补齐）

| 节点 | 当前已覆盖 | 缺口 | 补充机制 | 落地动作 |
|---|---|---|---|---|
| 1 Message Ingress | schema 校验、任务连续性 | 缺少重入保护与风暴控制 | **Idempotency Key + Rate Limit Policy** | 同一 `message_id` 仅处理一次，超频进入队列限流 |
| 2 before_task | 规则召回、经验召回 | 缺少规则版本固定 | **Rule Version Pinning** | 本轮任务固定 `rule_set_version`，任务中途不得漂移 |
| 5 Skill Routing | score/threshold/trust | 缺少并列分数仲裁与放弃机制 | **Tie-breaker Policy + Abstain Gate** | 分差 < ε 时进入 review；无可信技能时允许 `abstain` |
| 6 Execute | done/constraint/validation | 缺少资源安全边界 | **Sandbox Policy + Timeout/Budget Guard** | 每子任务设置 CPU/时长/调用预算，超限即中断 |
| 8 after_task | outcome/summary/proposal | 缺少跨子任务一致性校验 | **Cross-subtask Consistency Check** | 汇总前检查结论、文件状态、依赖一致性 |
| 9 Memory Ingest | append/classify | 缺少去重与 schema 演进策略 | **Dedup Policy + Schema Migration Guard** | 相同 evidence hash 去重；不兼容 schema 进隔离区 |
| 11 Proposal Processor | 聚类与证据聚合 | 缺少优先级与重复提案抑制 | **Proposal Priority Queue + Similarity Merge** | 相似提案合并，按影响面/风险排序 |
| 12 Governance Gate | review/canary/rollback | 缺少审批配额与冻结窗口 | **Reviewer Quorum + Freeze Window Policy** | 高风险需双审；发布冻结期仅允许紧急修复 |
| 13 Memory Lifecycle | promote/archive/forget | 缺少语义漂移监测 | **Drift Detector + Auto-demotion Rule** | 命中率/冲突率下穿阈值自动降级 |
| 14 File Governance | 分类与权限 | 缺少所有权与事务化补丁 | **Ownership Lock + Transactional Patch Apply** | 非 owner 改动走 review；补丁失败自动回滚 |

### 必加审计字段（新增）
- `idempotency_key`
- `rule_set_version`
- `abstain_reason`
- `execution_budget`
- `consistency_check_result`
- `evidence_hash`
- `proposal_priority`
- `review_quorum`
- `drift_score`
- `ownership_lock_id`
