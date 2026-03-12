# Memory DB Unified Schema Plan (2026-03-12)

## Goals
- 每条消息任务（含定时任务/用户消息）都形成独立 `task_runs` 记录。
- 主动学习、Notebook经验、Notebook反思/提案/规则、语义层与图谱层分表。
- 统一跨表字段命名，降低转换成本。

## Unified Field Conventions
- `*_id`: 主键或外键（如 `task_id`, `event_id`, `notebook_exp_id`）
- `source`: 数据来源（telegram/cron/rss/feedback_button/...）
- `content`: 主文本内容
- `created_at` / `updated_at`: 写入与更新时间
- `status`: 生命周期状态（new/pending/applied/...）
- `significance`: routine/notable/pivotal
- `metadata_json`: 扩展字段容器

## Table Layers
1. **Task feedback layer**
   - `task_runs`: 每条消息任务一次写入，默认 `satisfaction=satisfied`。
2. **Active learning layer**
   - `external_learning_events`: 外部源采集事件（RSS/X/Moltbook 等）。
3. **Notebook experience layer**
   - `notebook_experiences`: 从任务总结提炼的 notebook 经验。
4. **Notebook reasoning layer**
   - `notebook_reflections`: notebook经验触发的反思。
   - `notebook_proposals`: notebook反思产出的提案。
   - `notebook_rules`: notebook提案沉淀的规则。
5. **Knowledge layer**
   - `graph_entities` / `graph_relations`: 图谱结构。
   - `semantic_knowledge`: 语义层，挂接实体与关系。

## Core Relations
- `task_runs.task_id -> notebook_experiences.task_id`
- `notebook_experiences.notebook_exp_id -> notebook_reflections.notebook_exp_id`
- `notebook_reflections.notebook_reflection_id -> notebook_proposals.notebook_reflection_id`
- `notebook_proposals.notebook_proposal_id -> notebook_rules.notebook_proposal_id`
- `graph_entities.id -> semantic_knowledge.entity_id`
- `graph_relations.id -> semantic_knowledge.relation_id`

## Conversion Path
1. Message task complete: write `task_runs`.
2. Passive extractor: `task_runs -> notebook_experiences`.
3. Reflection engine: `notebook_experiences -> notebook_reflections`.
4. Governance: `notebook_reflections -> notebook_proposals -> notebook_rules`.
5. Knowledge consolidation: `notebook_* + memories -> graph_* + semantic_knowledge`.

## Notes
- 现有 `memories/proposals/reflections/rules` 仍保留为兼容与全局索引层。
- 新增分层表用于明确来源与职责，避免不同数据形态混写。
