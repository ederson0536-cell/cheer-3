# memory/ README

这个目录是系统的持久化记忆空间。每个子目录有明确职责，避免混写。

## 核心规则

- **DB-first**：运行时统一读写 `memory.db`。
- **JSONL 仅兼容**：`*.jsonl` 仅用于迁移、归档或调试投影，不作为运行主路径。
- **可追溯**：关键改动必须带时间、来源与上下文。

## 目录职责（精简版）

- `experiences/`：会话经验日志（JSONL）
  - 何时改：每次有实质性交互时追加。
- `proposals/`：提案与审批队列
  - 何时改：提案状态流转时。
- `reflections/`：反思产物
  - 何时改：反思任务产出新结果时。
- `tasks/`：任务执行轨迹
  - 何时改：任务生命周期事件发生时。
- `governance/`：治理审计与策略执行记录
  - 何时改：评审/发布/回滚/文件治理动作发生时。
- `working/`：运行中的临时工件
  - 何时改：执行期写入；过期可归档/清理。

## 机器可读清单

- `evoclaw/runtime/config/memory_directory_registry.json`
- `evoclaw/runtime/config/root_file_registry.json`

## 数据库盘点表

- `memory.db.system_catalog`：任务/文件数量与分类统计。
- `memory.db.system_readable_checklist`：可读职责清单（根文件 + memory 目录）。
