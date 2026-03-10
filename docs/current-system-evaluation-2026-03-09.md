# Cheer 当前系统评估（2026-03-09）

## 1. 总体评价

当前 Cheer 已从“多入口 + 文件主写 + 弱观测”的状态，演进到“入口基本收敛 + DB-first 主干 + 可观测可审计”的状态，具备上线运行基础。

**综合评级：B+（可运行，仍需做架构收口）**

- **稳定性：B+**（迁移链路与幂等能力已补齐核心短板）
- **一致性：B**（主数据已收敛到 `memory.db`，但仍有部分 json/jsonl 历史路径）
- **可观测性：B+**（已有关键计数器和 `/health` 1h 失败率）
- **可维护性：B**（遗留多适配器、多历史模块并存）

---

## 2. 已达成能力（确认项）

### 2.1 入口与处理链

- 已建立统一 ingress 路由：`ingress_router.route_message(...)`。
- `MessageHandler` 仍是核心处理器，前后 hook 与运行时逻辑可统一承载。
- 入口 metadata 已包含 `trace_id/source/channel`，并补充 `message_id`。

### 2.2 幂等与去重

- 入口生成统一 `message_id`（原始 id + sender + 分钟窗口 hash）。
- 会话写入使用稳定 id（`conversation-{message_id}`）。
- SQLite upsert 使用冲突更新策略，重复投递会合并为同一记录更新。

### 2.3 记忆系统与迁移

- `memory.db` 作为主写源的策略已落地（ownership contract + validator）。
- 迁移脚本对 legacy 缺失场景更稳健，`test_sqlite_memory` 已可作为回归门槛。

### 2.4 观测性

- 已具备关键指标：
  - `ingress_total`
  - `handler_success_total`
  - `handler_error_total`
  - `db_write_success_total`
  - `db_write_failed_total`
  - `dropped_message_total`
- API 层提供 `/health`，可输出最近 1h 失败率。

---

## 3. 主要风险（仍需治理）

1. **历史模块并存**：适配器与旧处理路径仍然较多，后续改动有回归分叉风险。  
2. **文件投影边界未完全收口**：部分 `memory/*.jsonl` 仍承担准主数据角色。  
3. **运维门禁未强制化**：`run_all.py` 已有检查项，但生产发布流程需硬绑定。  
4. **健康阈值告警策略待细化**：目前有失败率输出，尚缺明确告警等级与自动处理策略。

---

## 4. 建议路线图（下一阶段）

## P0（1 周内）

- 将所有 transport 入口明确标注为“adapter-only”，禁止新增业务分支。
- 对 `memory/tasks`、`memory/working` 等高频路径建立 DB 镜像写并做一致性对比。
- 在 CI / 发布脚本中强制：`test_sqlite_memory` + 关键 validators 全绿才可合并。

## P1（2~3 周）

- 完成“文件投影化”：将非归档 json/jsonl 写入迁至 `memory/projections` 目录语义。
- 增加 `/health` 阈值判断输出（ok/warn/critical）和最近 1h 错误 TopN 来源。
- 统一重试队列消费器，避免失败重试文件长期堆积。

## P2（1 个月）

- 清理 legacy handlers（降级到 `legacy/` 或 `examples/`）。
- 建立端到端回放包（Telegram 文本、语音、重复消息、DB 暂时不可写场景）。

---

## 5. 运维结论

结论：**当前系统可进入持续运行阶段，但应在“入口唯一化 + 文件投影化 + 发布门禁硬约束”三项上继续推进，避免后续复杂度反弹。**
