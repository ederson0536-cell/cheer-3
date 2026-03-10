# OpenClaw / EvoClaw 详细使用手册（2026-03-10）

> 面向对象：系统维护者、功能开发者、运营值班人员。  
> 目标：快速上手系统、理解主链路、会做日常检查、能定位常见问题。

---

## 1. 系统是什么

本系统是一个“统一入口 + 任务执行 + 记忆沉淀 + 文件治理 + 审计回放”的运行框架：

- 所有消息应走统一入口（ingress router）。
- 任务执行前后通过 hooks 写入经验/反馈。
- 关键状态进入 SQLite（`memory/memory.db`）。
- 文件修改受 file catalog + policy 约束。
- 可通过 validators 做一致性与回归检查。

---

## 2. 目录与关键文件

### 2.1 根目录关键文件

- `AGENTS.md`：工作区行为规范。
- `SOUL.md`：代理身份约束（CORE/MUTABLE）。
- `USER.md`：用户画像信息。
- `MEMORY.md`：长期记忆摘要。
- `TOOLS.md`：本地工具与环境操作说明。

### 2.2 运行与配置

- `evoclaw/runtime/ingress_router.py`：统一入口、幂等、限流。
- `evoclaw/runtime/message_handler.py`：任务链执行入口。
- `evoclaw/runtime/components/file_governance.py`：文件治理核心。
- `evoclaw/runtime/config/root_file_registry.json`：根文件职责/改动触发。
- `evoclaw/runtime/config/memory_directory_registry.json`：memory 子目录职责/改动触发。

### 2.3 记忆目录

- `memory/README.md`：memory 目录职责说明。
- `memory/memory.db`：主数据库。
- `memory/experiences/*.jsonl`：经验日志（append-only）。

---

## 3. 消息处理主链路

```
外部消息
  -> route_message()  (ingress_router)
      -> envelope 构建
      -> idempotency 检查
      -> rate-limit 检查
      -> continuity_resolver
      -> MessageHandler.handle()
          -> before_task
          -> task analyze / execute
          -> after_task
          -> feedback 写库
```

### 3.1 幂等策略

- 基于 `message_id` / 外部 id + 发送者 + 时间窗口生成 `idempotency_key`。
- 已处理 key 重复进入时会被阻断并打点。

### 3.2 限流策略

- 默认按 channel 做滑动窗口限流。
- 超限返回 blocked 响应并记录指标。

---

## 4. 数据库使用指南（`memory/memory.db`）

## 4.1 关键表

- `memories`：经验与记忆对象。
- `system_logs`：系统日志（含 feedback hook）。
- `system_catalog`：系统盘点（任务总数、文件总数、分类计数等）。
- `system_readable_checklist`：可读职责清单（root_file / memory_directory）。

### 4.2 常用查询

```sql
-- 看系统盘点
SELECT object_key, object_count
FROM system_catalog
ORDER BY object_key;

-- 看可读清单（根文件）
SELECT checklist_id, target_path, purpose, when_to_change
FROM system_readable_checklist
WHERE checklist_type='root_file'
ORDER BY checklist_id;

-- 看可读清单（memory 目录）
SELECT checklist_id, target_path, purpose, when_to_change
FROM system_readable_checklist
WHERE checklist_type='memory_directory'
ORDER BY checklist_id;

-- 看最近反馈 hook
SELECT created_at, source, log_type, content
FROM system_logs
WHERE log_type='feedback_hook'
ORDER BY created_at DESC
LIMIT 20;
```

---

## 5. 文件治理使用指南

### 5.1 刷新目录库

```bash
python3 scripts/build_file_catalog_db.py \
  --root . \
  --db memory/file_catalog.sqlite \
  --memory-db memory/memory.db
```

执行后会更新：

- `file_catalog`（文件级治理元信息）
- `system_catalog`（统计盘点）
- `system_readable_checklist`（职责清单）

### 5.2 策略语义

- `file_class=CORE`：高风险，通常 `review-only`。
- `primary_function`：文件主要作用。
- `change_trigger`：可改动条件。

---

## 6. 任务完成后的反馈接口对齐

标准检查点：

1. 入口调用成功（`route_message` 返回正常）。
2. `after_task` 执行后，`system_logs` 出现 `feedback_hook` 记录。
3. `feedback_hook.content` 结构包含：
   - `hook=after_task`
   - `task` 对象
   - `result` 对象

如果第 2/3 项缺失，优先排查：

- `after_task` hook 是否抛错。
- 数据库写入是否失败（看 `system_logs` 中 error 级记录）。

---

## 7. 一键校验（建议日常执行）

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python evoclaw/validators/validate_system_coordination.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python evoclaw/validators/validate_week2_ingress_continuity.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. python evoclaw/validators/validate_week5_file_governance.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=. pytest -q evoclaw/validators/test_sqlite_memory.py
```

含义：

- `validate_system_coordination`：跨模块一致性（写库 + 反馈 + 清单）
- `validate_week2_ingress_continuity`：入口幂等/限流/连续性
- `validate_week5_file_governance`：文件治理 precheck/enforce
- `test_sqlite_memory`：数据库 schema 与迁移/接口回归

---

## 8. 常见问题排查

### Q1：消息进入了，但没有反馈日志

- 看 `system_logs` 是否有 `feedback_hook`。
- 没有则检查 `after_task` 是否被执行。
- 检查写库错误计数与异常日志。

### Q2：catalog 构建报唯一键冲突

- 确认已使用最新脚本（`file_id` 基于 path 哈希）。
- 删除异常旧库后重建：
  - `memory/file_catalog.sqlite`

### Q3：清单表为空

- 检查配置文件是否存在：
  - `evoclaw/runtime/config/root_file_registry.json`
  - `evoclaw/runtime/config/memory_directory_registry.json`
- 重新执行 `build_file_catalog_db.py`。

---

## 9. 运维建议

- 每日最少跑一次第 7 节四条校验命令。
- 任何策略改动后，先跑 validators 再合并。
- 发布前保留一份 `system_catalog` 与 `system_readable_checklist` 快照，便于对比回归。

---

## 10. 版本记录

- 2026-03-10：首次发布详细使用手册。
