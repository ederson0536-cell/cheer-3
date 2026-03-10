# Week4 落实与验证报告（Execution Plan v1.1）

## 已落实项

1. Memory Ingest（去重 + 迁移守卫）
   - 新增 `memory_lifecycle` 组件，提供 append-only ingest。
   - 增加 schema migration guard（仅允许已支持 schema_version）。
   - 增加 dedup fingerprint，重复事件不重复写入并记录 dedup 命中。
2. Memory Recall 优先级收口
   - `memory_retrieval.retrieve` 新增 `recall_priority_order = [rules, experience, candidate]`。
   - 新增结构化 `recall_packet`，按固定层级输出检索结果。
3. Proposal Processor（优先队列 + 相似合并）
   - 新增 `priority_score` 计算和 `get_priority_queue`。
   - 相同 fingerprint proposal 自动 merge，累计 `merge_count`。
   - 输出可观测统计 `processor_stats.json`（added/merged）。
4. Governance Gate（review quorum + freeze window）
   - 引入 `review_quorum` 审批票数门槛。
   - 引入 `freeze_windows` + `enforce_freeze_window` 配置。
   - candidate/review_pending 对象默认 review-only，不走自动审批。
5. Promotion / Retention Skeleton
   - `promotion_guard`：candidate → semantic/active 必须 review + threshold。
   - `run_retention`：working/buffer 过期归档、recovery 月度归档骨架。

## 验证命令

- `python3 evoclaw/validators/validate_canonical_alignment.py`
- `python3 evoclaw/validators/validate_state_transitions.py`
- `python3 evoclaw/validators/validate_week2_ingress_continuity.py`
- `python3 evoclaw/validators/validate_week3_runtime_gates.py`
- `python3 evoclaw/validators/validate_week4_memory_proposal.py`
- `python3 -m py_compile evoclaw/runtime/components/memory_lifecycle.py evoclaw/runtime/components/proposal_processor.py evoclaw/runtime/components/governance.py evoclaw/runtime/components/memory_retrieval.py evoclaw/runtime/hooks/after_task.py evoclaw/runtime/hooks/after_subtask.py evoclaw/runtime/components/candidate_memory.py`

## 结论

Week4 的“记忆与提案”最小闭环已具备：
- ingest 去重与迁移守卫可执行；
- recall 顺序固定且可审计；
- proposal 可优先级排序并做相似合并；
- governance 已具备 quorum/freeze 机制；
- promotion/retention 有最小可运行骨架并可验证。
