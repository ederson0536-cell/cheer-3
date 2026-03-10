# EvoClaw Cheer 运行与使用手册（详细版）

> 适用对象：维护 Cheer 的开发/运维同学。
> 
> 目标：用一套可重复流程完成“启动、验证、观测、排障、回归、发布”。

---

## 1. 当前系统结构（先理解再操作）

## 1.1 消息主链路

```text
Transport (Telegram/API/CLI)
  -> runtime.ingress_router.route_message()
  -> runtime.message_handler.MessageHandler.handle()
  -> hooks (before_task / after_task)
  -> feedback_system / sqlite_memory
  -> memory/memory.db
```

关键点：

- 入口统一在 `route_message(...)`。
- 入口会注入 `trace_id/source/channel/timestamp/message_id`。
- `message_id` 用于去重与幂等写入。

## 1.2 幂等策略

- `message_id` 计算：`raw_message_id + sender + minute-window hash`。
- conversation 写入 id：`conversation-{message_id}`。
- DB 层 `upsert_experience` 采用冲突更新，重复消息不会重复入库。

## 1.3 观测指标

已接入指标：

- `ingress_total`
- `handler_success_total`
- `handler_error_total`
- `db_write_success_total`
- `db_write_failed_total`
- `dropped_message_total`

健康检查：

- `GET /health` 返回最近 1h 的 handler/db 失败率。

---

## 2. 启动方式

## 2.1 CLI 单条消息测试

```bash
cd /workspace/claw/workspace-cheer
python3 evoclaw/run.py "你好，做个系统检查"
```

## 2.2 API 服务

```bash
cd /workspace/claw/workspace-cheer
python3 evoclaw/runtime/api_server.py
```

默认端口：`8899`

---

## 3. API 使用手册

## 3.1 发送消息

```bash
curl -sS -X POST http://127.0.0.1:8899 \
  -H 'Content-Type: application/json' \
  -H 'X-Trace-Id: demo-trace-1' \
  -d '{
    "message": "请总结今天的修复进展",
    "raw_message_id": "tg-1001",
    "sender": "alice",
    "timestamp": "2026-03-09T10:00:12"
  }'
```

返回包含：

- `ingress.message_id`
- `handler_result`
- `handler_status`

## 3.2 健康检查

```bash
curl -sS http://127.0.0.1:8899/health | python3 -m json.tool
```

重点字段：

- `counters_last_hour`
- `failure_rates_last_hour.handler_failure_rate`
- `failure_rates_last_hour.db_write_failure_rate`

---

## 4. 日常运行检查（建议顺序）

## 4.1 工作区边界

```bash
cd /workspace/claw/workspace-cheer
python3 evoclaw/validators/check_workspace.py
```

## 4.2 记忆表契约

```bash
python3 evoclaw/validators/check_memory_db_ownership.py
```

## 4.3 路径硬编码检查

```bash
python3 evoclaw/validators/check_no_hardcoded_workspace_path.py
```

## 4.4 SQLite 主回归

```bash
python3 -m unittest evoclaw.validators.test_sqlite_memory -v
```

## 4.5 总体验证编排

```bash
python3 evoclaw/validators/run_all.py
```

> 注：若缺少 `memory/evoclaw-state.json` 或当日 experiences 文件，`run_all.py` 可能因环境数据缺失报 FAIL。

---

## 5. 故障排查手册

## 5.1 消息未入库

1. 看入口是否到达：`logs/message_handler.jsonl`。
2. 看健康与计数器：`/health` 是否 `ingress_total` 增长。
3. 看 DB 失败计数：`db_write_failed_total` 是否增长。
4. 查重试队列：`memory/retry/db_write_failures.jsonl`。

## 5.2 重复消息

1. 检查返回中的 `ingress.message_id` 是否一致。
2. 在 DB 中按 `metadata_json.message_id` 或记录 id 查询。
3. 确认上游是否正确提供 `raw_message_id/sender/timestamp`。

## 5.3 handler 错误率上升

1. `/health` 查看 `handler_failure_rate`。
2. 查询 `system_logs` 中 `metric_counter` + `handler_error_total`。
3. 结合 `message_handler.jsonl` 定位具体输入与异常路径。

---

## 6. 迁移与数据治理

## 6.1 全量迁移

```bash
python3 scripts/migrate_all_to_sqlite.py --memory-root memory --db-path memory/memory.db
```

## 6.2 经验表结构迁移

```bash
python3 scripts/migrate_experience_schema_v2.py --db-path memory/memory.db
```

## 6.3 验收

```bash
python3 -m unittest evoclaw.validators.test_sqlite_memory -v
```

---

## 7. 发布前清单（Go/No-Go）

必须满足：

- `check_workspace.py` PASS
- `check_memory_db_ownership.py` PASS
- `check_no_hardcoded_workspace_path.py` PASS
- `test_sqlite_memory` 全绿
- `/health` 最近 1h `handler_failure_rate` 与 `db_write_failure_rate` 在可接受范围

建议阈值（可按环境调整）：

- `handler_failure_rate < 0.05`
- `db_write_failure_rate < 0.01`

---

## 8. 运维建议（长期）

- 严禁新增“绕过 ingress_router 的业务入口”。
- 业务主写一律先入 `memory.db`，json/jsonl 仅做投影或归档。
- 每次改动入口、hook、持久化逻辑，都跑最小回归：
  - workspace + ownership + sqlite_memory + health smoke。
