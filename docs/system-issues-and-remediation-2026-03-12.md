# 系统问题巡检与整改建议（2026-03-12）

## 巡检结论（摘要）
当前系统主路径可运行（wiring/test 通过），但仍存在“设计目标与实现细节未完全对齐”的问题，主要集中在：
1. **每条消息独立任务语义未彻底收敛**（仍保留 continuity 强依赖与遗留逻辑）。
2. **新分层表已建，但写入/查询链路不完整**（仅部分表有 DAO）。
3. **跨表关系仅文档化，数据库未做约束**（缺少 FK 与一致性保护）。
4. **反馈回调与普通消息共用入口，字段语义可能冲突**。
5. **运行时出现 before_task 检索降级告警**（数据质量/兼容性问题仍在）。

---

## 问题 1：每条消息独立任务语义未彻底收敛

### 现象
- `REQUIRED_CHAIN_FIELDS` 仍强制 `continuity_resolution`，与“每条消息独立任务”目标不完全一致。
- 仍保留 `_handle_continuation` 方法与相关状态结构，形成“语义上已弃用、代码上仍存在”的维护负担。

### 证据
- `REQUIRED_CHAIN_FIELDS` 仍包含 `continuity_resolution`。  
- `_handle_continuation` 仍存在（虽标注 deprecated）。

### 整改建议
1. 将 `continuity_resolution` 从硬依赖降为可选字段，仅保留审计/分析用途。
2. 删除 `_handle_continuation` 与对应状态分支，MessageHandler 仅保留 `single_message_task` 路径。
3. 为“每条消息独立任务”增加契约测试（禁止回归到 continuation 分叉）。

---

## 问题 2：新分层表已建，但数据访问层尚不完整

### 现象
- 已新增 `notebook_reflections/notebook_proposals/notebook_rules/semantic_knowledge` 等表。
- 但当前 `sqlite_memory.py` 仅提供 `upsert_external_learning_event` 与 `upsert_notebook_experience`，其余新增表尚无对称 upsert/query API，影响落地。

### 整改建议
1. 为新增每张表补齐最小 DAO：`upsert_*`, `query_*`, `mark_status_*`。
2. 补配套转换任务：
   - `task_runs -> notebook_experiences`
   - `notebook_experiences -> notebook_reflections -> notebook_proposals -> notebook_rules`
3. 在 cron/heartbeat 增加“表级写入计数”与空跑告警。

---

## 问题 3：跨表关系未做数据库级约束

### 现象
- 关系在文档/contract 已定义（如 `task_runs.task_id -> notebook_experiences.task_id`），但 SQLite schema 未声明外键约束。
- 目前主要靠应用层约定，存在孤儿数据风险。

### 整改建议
1. 为 notebook 链路补 FK（可先软约束：启动时 consistency check）。
2. 增加 nightly 数据校验：孤儿记录、状态流转异常、时间戳逆序。
3. 在 `validate_wiring_coverage` 加入“关系完整性 SQL 检查”。

---

## 问题 4：反馈回调与普通消息共用 `/message` 入口，字段有歧义风险

### 现象
- `/message` 同时处理“普通消息”和“反馈按钮”。
- `feedback_message` 与普通 `message` 在回调场景会复用文本字段，若上游 payload 不稳定，可能被误判路径。

### 整改建议
1. 建议拆分为 `/message`（纯消息）与 `/feedback`（纯按钮回调）两个端点。
2. 若暂不拆分，至少要求 `event_type=feedback_button` 明确区分。
3. 对回调 payload 增加签名字段和 schema 校验（callback_data 版本号）。

---

## 问题 5：before_task 检索链路仍存在降级告警

### 现象
- 单测运行日志里持续出现：`runtime before_task skipped: Expecting value...`。
- 说明检索链路在某些历史数据上存在 JSON 解码/兼容问题，当前靠 fallback 兜底。

### 整改建议
1. 为历史坏数据做一次性修复脚本（清洗非法 JSON 字段）。
2. 在读取层统一 `safe_json_loads`，写入层加强 schema 校验。
3. 将该告警纳入监控指标（超过阈值报警）。

---

## 建议的分阶段整改路线

### Phase A（1-2 天）
- 收敛 message handler：移除 continuation 强依赖与遗留分支。
- 拆分反馈端点或补 event_type 强约束。
- 增加回归测试：每条消息只走单任务链路。

### Phase B（2-4 天）
- 补齐新增分层表 DAO 与状态流转任务。
- 增加表级指标与 consistency check。

### Phase C（3-5 天）
- 引入 FK/软约束双保险。
- 做历史数据清洗并验证 before_task 无降级。

---

## 验收标准（建议）
1. 连续 24h 内 `runtime before_task skipped` 告警为 0。
2. `task_runs` 与 `notebook_*` 表转换链路每日有稳定写入计数。
3. 任意时间点抽检不存在 notebook 孤儿记录。
4. 端到端消息处理仅存在单任务路径（无 continuation 分叉）。
