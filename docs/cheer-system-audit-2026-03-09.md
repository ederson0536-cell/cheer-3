# Cheer 全量审计与整改方案（2026-03-09）

## 审计范围与方法
- 范围：`workspace-cheer` 全仓（约 9523 个文件，包含代码、脚本、日志、记忆数据）。
- 方法：结构扫描 + 关键链路静态审计 + 现有测试验证。
- 重点链路：`Telegram/OpenClaw ingress -> feedback_trigger -> message_handler -> hooks -> memory.db -> cron/reflection/proposal`。

## 关键结论

### 1) 文本消息入口的主链路已可接入 handler，但系统仍存在“多入口并行”风险
- `feedback_trigger.py` 现在已路由到 `MessageHandler.handle()`，具备统一处理能力。
- 但仓库中并行存在多个入口/处理器（`run.py`、`api_server.py`、`integrated_handler.py`、`auto_handler.py`、`wrapper.py`、`cron_runner.py` 的补偿逻辑），容易造成“同一条消息被不同逻辑处理或漏处理”。

### 2) 路径硬编码问题仍然广泛
- 代码中大量残留 `/home/bro/.openclaw/workspace-cheer` 硬编码，覆盖 runtime、hooks、components、脚本等。
- 这会导致跨环境部署（容器、CI、不同用户目录）时出现隐性故障（找不到文件、写入到错误位置）。

### 3) 执行层与进化层对 memory.db 的对接是“部分统一 + 部分并行”
- 一部分写入已走 `SQLiteMemoryStore`。
- 另一部分仍以 json/jsonl 文件为主（例如 `memory/tasks/*.jsonl`、`memory/working/*.json`、`memory/subtasks/*.jsonl`）。
- 结果：存在双写与数据漂移风险，且回放/一致性验证成本高。

### 4) 错误处理中存在大量“吞异常”
- 多个关键路径使用裸 `except:` 或 `except Exception: pass`。
- 这会把“写入失败/处理失败”降级为静默丢失，表面流程继续，但数据不完整。

### 5) 迁移脚本与测试已暴露实际缺陷
- `test_sqlite_memory` 当前有两项失败：
  - `test_migrate_all_script_imports_all_tables`：`candidates` 计数不达预期。
  - `test_migrate_experience_schema_v2_from_legacy_table`：迁移脚本在无 `experience_events` 表时直接报错。
- 这说明“历史数据迁移链路”并不稳定，不能作为生产可依赖路径。

## 证据索引（关键文件）

### A. 文本消息与 cron 补偿链路
- `cron_runner.py` 依赖 `logs/message_handler.jsonl` 导入会话经验，并在无日志时直接跳过。 
- `cron_runner.py` 同时存在 `_process_recent_messages()` 的“读取最后一条日志再回调 handler”补偿逻辑。

### B. Hook 与 memory 写入
- `message_handler.py` 的 `handle()` 已固定执行 `before_task` / `after_task`。
- `feedback_system.py` 的 `after_task()` 会写 conversation memory、feedback log、proposal/reflection 投影。

### C. 文件化记忆仍在主流程中
- `runtime/hooks/before_task.py`、`after_task.py`、`after_subtask.py` 仍把关键状态写入 `memory/**/*.json|jsonl`。

### D. 迁移链路缺陷
- `scripts/migrate_experience_schema_v2.py` 在未检测到 legacy 表时，仍直接查询 `experience_events`，导致特定库结构下崩溃。
- `validators/test_sqlite_memory.py` 已有用例明确断言并失败。

## 详细整改方案（按优先级）

## P0（本周必须完成）

1. **单一消息入口收敛（Ingress Router）**
   - 定义唯一入口：`message_handler.get_handler().handle(message)`。
   - 其他入口（`api_server`/`integrated_handler`/`auto_handler`/`run.py`）只做 transport adapter，不再各自实现业务流程。
   - 在入口处统一注入 `trace_id/source/channel`，避免重复处理。

2. **去除关键路径裸异常吞噬**
   - 对 `feedback_system.py`、`cron_runner.py`、`runtime/hooks/*`、`runtime/components/*` 的关键写入点：
     - 禁止 `except: pass`。
     - 改为：结构化错误日志 + 错误计数器 + 可选重试队列。
   - 对 DB 写入失败，至少落 `system_logs(level=error)`。

3. **路径统一策略（WorkspaceResolver）**
   - 新建统一的 `resolve_workspace()`（单模块），使用 `Path(__file__)` + env 覆盖。
   - 所有 `/home/bro/.openclaw/workspace-cheer` 替换为 resolver。
   - CI 增加“禁止硬编码路径”检查（rg 规则 + fail build）。

4. **修复迁移脚本稳定性**
   - 修复 `migrate_experience_schema_v2.py`：在不存在 `experience_events` 时返回 `0` 而非异常。
   - 修复 `migrate_all_to_sqlite.py` 对 `candidates` 的导入遗漏。
   - 以 `test_sqlite_memory` 两个失败用例为验收门槛（必须转绿）。

## P1（两周内）

5. **记忆系统“单写源”收敛**
   - 目标：执行态/进化态主数据统一入 `memory.db`。
   - `json/jsonl` 改为：
     - 可选投影（report/debug）
     - 或归档快照
   - 明确每张表与字段来源，定义 ownership。

6. **观测性与健康度**
   - 新增指标：
     - ingress_total / handler_success_total / handler_error_total
     - db_write_success_total / db_write_failed_total
     - dropped_message_total
   - 新增 `/health`（或 cron 报告）输出最近 1h 失败率。

7. **去重与幂等策略**
   - 入口层写入统一 `message_id`（渠道原始 id + sender + 时间窗口 hash）。
   - DB 层增加唯一索引或冲突更新策略，避免重复入库。

## P2（一个月）

8. **架构分层整理**
   - transport（Telegram/OpenClaw/Web）
   - orchestration（MessageHandler）
   - domain（hooks / runtime）
   - persistence（SQLiteMemoryStore）
   - 把“脚本时代”代码（多个 handler 变体）降级到 examples/legacy。

9. **端到端回归包**
   - 建立文本消息/语音消息/失败恢复/迁移回放 E2E 套件。
   - 在 PR 阶段执行 smoke + migration + e2e 最小集。

## 建议的实施顺序（最小风险）
1) 先修迁移脚本与异常吞噬（不改主业务流）。
2) 再做入口收敛与路径统一（可灰度：保留旧入口但转发到统一 handler）。
3) 最后做 memory 单写源与表级 ownership 收敛。

## 验收标准（Definition of Done）
- 文本消息从 Telegram 进入后，100% 出现：
  - `logs/message_handler.jsonl` 的 receive + result 事件
  - `memories(type=conversation, source=message_handler)` 记录
- `test_sqlite_memory` 全绿（当前两项失败归零）。
- 仓库扫描无新增硬编码绝对路径。
- 关键路径无裸 `except: pass`。
