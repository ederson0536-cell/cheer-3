# Cheer-3 系统详细使用手册（2026-03-10）

## 1. 系统概览

Cheer-3 是一个围绕 **EvoClaw/OpenClaw** 运行的自动化助手工作区。

> 当前版本已切换为 **数据库（memory.db）单一读写源**：运行时与巡检默认都以 SQLite 为准，不再依赖 JSONL 作为运行时输入。

核心由以下模块组成：

- **入口层（Ingress）**：统一接收消息并做去重、限流、连续性解析。
- **执行层（Runtime）**：根据任务路由技能、执行 Hook、调用记忆与治理模块。
- **记忆层（Memory）**：将 experience / proposal / reflection / state 持久化到 JSONL 与 SQLite。
- **验证层（Validators）**：对结构完整性、链路一致性、治理约束做自动巡检。

---

## 2. 目录速览（运维常用）

- `evoclaw/runtime/`：运行时入口、hook、组件。
- `evoclaw/validators/`：系统校验脚本（建议先跑 `run_all.py`）。
- `memory/`：状态与经验数据。
- `docs/`：审计报告、治理文档与本手册。
- `logs/`：运行日志（消息、技能执行、学习过程等）。

---

## 3. 快速启动与日常巡检

### 3.1 环境前置

- Python 3.11+（当前仓库实测 3.12 可用）。
- 工作目录必须是仓库根目录：`/workspace/cheer-3`。

### 3.2 一键巡检（推荐）

```bash
python3 evoclaw/validators/run_all.py
```

判定规则：
- `Overall: PASS`：可继续运行。
- `Overall: FAIL`：先按报错修复，再继续任务。

### 3.3 单项排查（常用）

```bash
python3 evoclaw/validators/validate_experience.py memory/memory.db --config evoclaw/config.json --date $(date +%F)
python3 evoclaw/validators/validate_state.py memory/evoclaw-state.json --memory-dir memory --proposals-dir memory/proposals
python3 evoclaw/validators/validate_system_coordination.py
```

---

## 4. 核心运行链路

### 4.1 消息入口链路

入口统一走 `evoclaw/runtime/ingress_router.py`：

1. 封装 envelope（带 `trace_id`, `session_id`, `message_id`）。
2. 基于 `message_id` 做幂等去重。
3. 基于 channel 做窗口限流。
4. 调用 continuity resolver 判定上下文连续性。
5. 进入 message handler 执行业务逻辑。

### 4.2 子任务执行链路

`before_subtask` Hook（`evoclaw/runtime/hooks/before_subtask.py`）执行：

- 技能路由（skill router）
- 局部经验召回
- 文件治理 precheck
- 子任务 checklist 生成

建议：凡是“改代码 + 产出文档”复合任务，都先确保 file scope 正确传递，否则治理校验可能拦截写入。

### 4.3 定时流程（cron_runner）

`evoclaw/cron_runner.py` 典型阶段：

1. Workspace 健康检查
2. INGEST：RSS + `task_runs` 被动提取 + notebook 分层投影
3. REFLECT：按 significance 分级，触发反思/提案
4. 治理与收尾：更新 state、写运行记录

---

## 5. 记忆系统使用规范

### 5.1 experience 数据（DB-first）

运行态以 `memory/memory.db` 的 `memories`（含 `experiences` 视图）为准。

推荐字段（写入 DB 前的标准 payload）：

```json
{
  "id": "EXP-YYYYMMDD-0001",
  "timestamp": "2026-03-10T20:00:00+00:00",
  "type": "conversation",
  "source": "conversation",
  "content": "用户要求检查系统并修复问题。",
  "significance": "notable"
}
```

兼容说明：
- 旧 JSONL 仅用于历史迁移与排障，不作为运行时 canonical 输入。
- 迁移建议使用 `scripts/migrate_experiences_to_sqlite.py` 导入 DB。

### 5.2 state 文件

`memory/evoclaw-state.json` 至少应包含：
- `today`
- `experience_count_today`
- `last_updated`（推荐）

若 `pending_proposals` 存在，应与 `memory/proposals/pending.jsonl` 行数一致。

### 5.3 proposal 与 reflection

- pending 提案统一放 `memory/proposals/pending.jsonl`。
- reflection 放 `memory/reflections/REF-*.json`。
- notable/pivotal 的 experience 应在反思后被标记或纳入反思输入，避免长期堆积。

---

## 6. 本次已修复的问题

### 问题 A：状态校验器缺失

现象：`run_all.py` 调用 `validate_state.py` 时直接报文件不存在，导致总校验失败。

修复：新增 `evoclaw/validators/validate_state.py`，支持：
- 文件存在与 JSON 结构检查
- `experience_count_today` 基本合法性检查
- `today` 日期偏差告警
- `pending_proposals` 与 pending.jsonl 一致性告警

### 问题 B：experience 旧格式触发大量误报

现象：历史 JSONL 使用 `ts/summary`，缺少 `id/source/content/significance`，导致 run_all 大量 FAIL。

修复：增强 `evoclaw/validators/validate_experience.py` 的旧格式归一化能力：
- `ts -> timestamp`
- `summary -> content`
- `type(notable/routine/pivotal) -> significance`
- 缺失字段自动补默认值与 legacy id

结果：系统从 `FAIL` 恢复为 `PASS`（保留兼容 warning，便于后续数据治理）。

---

## 7. 故障排查手册（Runbook）

### 场景 1：run_all 显示 experiences FAIL

1. 看错误是否为 `Missing id/source/content`。
2. 若为历史文件，先确认已升级到当前 validate_experience 版本。
3. 若是新写入数据，修复写入方，确保按标准字段落盘。

### 场景 2：state ERROR/FAIL

1. 检查 `memory/evoclaw-state.json` 是否存在且为合法 JSON。
2. 执行：
   ```bash
   python3 evoclaw/validators/validate_state.py memory/evoclaw-state.json --memory-dir memory --proposals-dir memory/proposals
   ```
3. 按 warning 修复计数不一致或日期漂移。

### 场景 3：入口层消息/反馈被拦截

1. 看是否 duplicate（幂等 key 重复）。
2. 看是否 rate limit（同 channel 单窗口超过阈值）。
3. 若是反馈回调，确认发送到 `/feedback`（不是 `/message`），且 `event_type=feedback_button`。
4. 检查 `X-Feedback-Signature` 与 `callback_data` 版本（`feedback:v1:...`）。
5. 再检查 `logs/message_handler.jsonl` 与 observability 指标。

---

## 8. 运维建议（强烈推荐）

- 每次系统改动后固定执行：`python3 evoclaw/validators/run_all.py`。
- 将历史 experience 渐进式迁移为标准 schema，减少 legacy warning。
- 对 `logs/` 定期归档，避免日志过大影响排障效率。
- 保持 `docs/` 里审计/手册文档按日期命名，便于回溯。

---

## 9. 常用命令清单

```bash
# 全量巡检
python3 evoclaw/validators/run_all.py

# 经验数据校验
python3 evoclaw/validators/validate_experience.py memory/memory.db --config evoclaw/config.json --date $(date +%F)

# 状态文件校验
python3 evoclaw/validators/validate_state.py memory/evoclaw-state.json --memory-dir memory --proposals-dir memory/proposals

# 系统协调性校验
python3 evoclaw/validators/validate_system_coordination.py

# 查看当前变更
git status --short
```

---

## 10. 版本备注

- 手册版本：`system-user-manual-2026-03-10`
- 维护建议：每次新增 validator 或 memory schema 变更后更新本手册。


## 11. 2026-03-12 链路更新（重点）

### 11.1 每条消息=独立任务

- `MessageHandler` 采用 single-message-task 语义。
- 每条消息完成后都写入一条 `task_runs`。
- 满意/不满意由按钮反馈驱动，不再使用自由文本确认状态机。

### 11.2 分层投影链路

- Cron Step1 被动学习从 `task_runs` 抽取 `task_execution` 经验（默认跳过 unsatisfied）。
- 同步执行：
  - `task_runs -> notebook_experiences`
  - `notebook_experiences -> notebook_reflections`
  - `notebook_reflections -> notebook_proposals`
  - `notebook_proposals -> notebook_rules`（仅 unsatisfied）
- 计数写入 `memory/evoclaw-state.json:last_notebook_projection_counts`。

### 11.3 回调接口约束

- 普通消息只走 `/message`。
- 反馈回调只走 `/feedback`，并要求：
  - `event_type=feedback_button`
  - `callback_data` 使用 `feedback:v1:<task_id>:<value>`
  - 配置密钥时校验 `X-Feedback-Signature`
