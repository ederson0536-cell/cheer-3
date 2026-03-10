# OpenClaw 最后收口表（State Machine / Outcome / Single Ingress）

## 1) System State Machine Table（统一状态机总表）

### 1.1 Task State

| 状态 | 含义 | 允许进入 | 允许流转到 |
|---|---|---|---|
| `new` | 新建任务，尚未开始执行 | 消息入队并通过 schema 校验 | `open`, `archived` |
| `open` | 已创建上下文，待调度 | continuity 已解析 | `in_progress`, `blocked`, `awaiting_review` |
| `in_progress` | 正在执行（含 subtask loop） | 调度器启动执行 | `blocked`, `awaiting_review`, `completed`, `failed` |
| `blocked` | 外部依赖不足或策略阻断 | 缺权限/缺资源/规则冲突 | `open`, `failed`, `archived` |
| `awaiting_review` | 需要人工或治理门审批 | 高风险写入/边界操作 | `in_progress`, `failed`, `archived` |
| `completed` | 通过 outcome 校验完成 | success path 达成 | `archived` |
| `failed` | 任务失败且不可在当前轮恢复 | retry 预算耗尽或硬失败 | `archived` |
| `archived` | 结束归档，仅读 | completed/failed/撤销 | - |

### 1.2 Proposal State

| 状态 | 含义 | 允许进入 | 允许流转到 |
|---|---|---|---|
| `draft` | 初稿提案（未形成证据包） | after hooks seed | `candidate`, `rejected` |
| `candidate` | 具备候选资格，待提交审查 | evidence 达最小阈值 | `review_pending`, `rejected` |
| `review_pending` | 正在审查中 | governance gate 收件 | `canary`, `rejected`, `archived` |
| `canary` | 小流量试运行 | 审批通过进入灰度 | `active`, `rolled_back`, `rejected` |
| `active` | 正式发布生效 | canary 指标达标 | `rolled_back`, `archived` |
| `rejected` | 审查否决 | evidence不足/风险过高 | `archived` |
| `rolled_back` | 发布后回滚 | canary/prod 指标下穿 | `archived` |
| `archived` | 提案生命周期结束 | active/rejected/rollback 结束 | - |

### 1.3 Memory Object State

| 状态 | 含义 | 允许进入 | 允许流转到 |
|---|---|---|---|
| `raw` | 原始事件（append-only） | ingest 首写 | `episodic`, `archived` |
| `episodic` | 可检索任务经验 | classify 成功 | `candidate`, `semantic`, `deprecated`, `archived` |
| `candidate` | 待验证记忆对象 | 证据聚合后生成 | `semantic`, `deprecated`, `archived` |
| `semantic` | 稳定记忆，可正式召回 | promote threshold 达标 | `deprecated`, `archived` |
| `deprecated` | 不推荐使用，降级保留 | 漂移/冲突/过期 | `archived` |
| `archived` | 历史归档 | 生命周期结束 | - |

### 1.4 File Object State

| 状态 | 含义 | 允许进入 | 允许流转到 |
|---|---|---|---|
| `active` | 当前生效文件版本 | 已发布文件 | `candidate_patch`, `locked` |
| `candidate_patch` | 待审补丁 | patch-first 生成差异 | `review_pending`, `rolled_back` |
| `review_pending` | 代码/策略评审中 | 高风险或核心文件改动 | `published`, `rolled_back` |
| `published` | 补丁已发布 | review/canary 通过 | `active`, `rolled_back` |
| `rolled_back` | 文件回滚态 | 发布后风险触发 | `active`, `locked` |
| `locked` | 写保护状态 | CORE / 冻结窗口 | `active` |

---

## 2) Task / Subtask Outcome Evaluation（统一 Outcome/Correctness/Success）

### 2.1 必填判定字段

- `interaction_success`
- `execution_success`
- `goal_success`
- `governance_success`
- `done_criteria_met`
- `constraint_check_passed`
- `validation_check_passed`
- `overall_outcome` (`success` / `partial` / `failure`)

### 2.2 判定规则

```text
correctness_pass = done_criteria_met
                  AND constraint_check_passed
                  AND validation_check_passed

overall_outcome =
  success  if interaction_success AND execution_success AND goal_success AND governance_success AND correctness_pass
  partial  if interaction_success AND (execution_success OR goal_success) AND governance_success AND NOT correctness_pass
  failure  otherwise
```

### 2.3 与下游模块绑定

- `failure taxonomy`：仅在 `overall_outcome != success` 时强制归类。
- `proposal processor`：`partial/failure` 自动生成 seed。
- `metrics`：success/partial/failure 三分统计，不再二元化。
- `review policy`：`governance_success=false` 直接升级到 mandatory review。

---

## 3) Single Ingress Policy（统一入口制度）

### 3.1 强制原则

1. 所有消息、事件、proposal review、自动触发任务，必须先封装成统一 `Envelope`。
2. 所有 Envelope 必须先经过 `continuity resolution`。
3. 所有任务必须先执行 `before_task`，再进入 subtask/skill 路由。
4. 不允许任何 skill/hook/script 绕过主链路直写执行结果或核心文件。

### 3.2 标准 Envelope（最小字段）

```json
{
  "envelope_id": "env_xxx",
  "source": "user|system|scheduler|review",
  "event_type": "message|trigger|proposal_review|heartbeat",
  "received_at": "ISO-8601",
  "payload": {},
  "idempotency_key": "...",
  "trace_context": {
    "root_task_id": null,
    "parent_task_id": null
  }
}
```

### 3.3 旁路防护

- 在执行器入口添加 `ingress_guard`：无 `envelope_id` 一律拒绝执行。
- 在文件写入前添加 `chain_guard`：无 `before_task` 轨迹一律阻断。
- 在审计中新增 `bypass_attempt_count` 与 `ingress_compliance_rate`。

