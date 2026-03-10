# 根目录文件治理清单（Root File Governance）

> 目的：让系统在改动前明确“每个根目录文件做什么、什么时候允许改动”。

## 数据源
- 机器可读配置：`evoclaw/runtime/config/root_file_registry.json`
- Memory 目录清单：`evoclaw/runtime/config/memory_directory_registry.json`
- 目录库：`memory/file_catalog.sqlite`（`file_catalog` 表）
- 系统盘点：`memory/memory.db`（`system_catalog` 表）
- 可读清单（独立表）：`memory/memory.db`（`system_readable_checklist` 表）

## 根目录关键文件职责

- `AGENTS.md`
  - 作用：工作区操作规则与行为约束
  - 改动触发：仅当治理规则/人类指令更新时
  - 默认策略：`CORE + review-only`

- `SOUL.md`
  - 作用：代理身份定义（CORE/MUTABLE）
  - 改动触发：仅通过 EvoClaw 提案/治理流程
  - 默认策略：`CORE + review-only`

- `USER.md`
  - 作用：用户画像与偏好上下文
  - 改动触发：用户明确给出新信息时
  - 默认策略：`CONTROLLED + review-only`

- `MEMORY.md`
  - 作用：长期记忆摘要
  - 改动触发：反思后沉淀稳定结论时
  - 默认策略：`CONTROLLED + review-only`

- `SYSTEM_FRAMEWORK_PROPOSAL.md`
  - 作用：系统架构与落地基线
  - 改动触发：框架契约/落地策略变更时
  - 默认策略：`CONTROLLED + review-only`

## 执行规则
1. 所有消息入口先经过 `ingress_router`，再进入任务链。
2. 文件修改前必须做 `file_catalog` precheck/enforce。
3. 扫描脚本刷新后，`system_catalog` 自动记录：
   - 任务总数（`tasks.total`）
   - 文件总数（`files.total`）
   - 各文件分类数量（`files.class.*`）
   - 根目录文件用途与改动触发（`root_file.*`）


## 独立可读清单（system_readable_checklist）
- `checklist_type = root_file`：根目录关键文件职责与改动条件。
- `checklist_type = memory_directory`：memory 子目录职责与改动条件。
- 用途：供后续扫描器/自动化变更策略直接查询，不必再解析 markdown。
