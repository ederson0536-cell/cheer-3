# 当前系统机制核查（2026-03-11）

## 1. 结论速览

当前仓库运行机制已经是 **DB-first + 统一入口路由 + 10 步学习闭环**：

- **统一消息入口**：`evoclaw/run.py` 与 `evoclaw/feedback_trigger.py` 都走 `route_message(...)`，保证同一条处理链（日志、钩子、记忆）
- **统一记忆底座**：`memory/memory.db` 为唯一主读写源，`experiences` 是 `memories` 视图，说明“经验”已并入统一表模型
- **学习/治理闭环**：`HEARTBEAT.md` 定义 10 步 EvoClaw pipeline（INGEST→REFLECT→PROPOSE→GOVERN→APPLY→LOG→STATE→NOTIFY→FINAL CHECK→REPORT）
- **治理模式**：`evoclaw/config.json` 当前为 `autonomous`，可自动应用符合规则的提案

---

## 2. 运行入口机制（Ingress）

### 2.1 CLI/脚本入口
- `evoclaw/run.py` 的 `run()` 直接把消息送入 `route_message(...)`。
- 这意味着任何通过 `python evoclaw/run.py "..."` 的调用，都会进入统一 runtime 路径。

### 2.2 Telegram 回调入口
- `evoclaw/feedback_trigger.py` 接收 `<sender> <message>` 后，构造 `[@sender] message` 再送入同一个 `route_message(...)`。
- 因此外部消息与本地调用不会出现两套处理逻辑分叉。

**机制价值：**
- 降低“某些入口没打日志/没进治理门”的概率
- 统一后更容易做回归和问题定位

---

## 3. 记忆机制（DB-first）

### 3.1 主存储
- `README.md` 已明确：运行态切到 DB-first，`memory/memory.db` 是单一读写源。
- `MEMORY.md` 也同步写明 `memory.db` 是运行时唯一主写源。

### 3.2 表结构与抽象
- `memory/memory.db` 中 `experiences` 为一个 SQL VIEW，底层来自 `memories`。
- `evoclaw/sqlite_memory.py` 创建了 `memories / proposals / reflections / graph_entities / graph_relations / soul_history / system_state` 等核心表与索引。

**机制价值：**
- 统一 schema + 索引，查询性能和一致性优于散落 JSONL
- `experiences -> memories` 的兼容视图保留了历史调用口径

---

## 4. 学习与治理机制

### 4.1 心跳主流程
- `HEARTBEAT.md` 给出完整 10-step 管道，并且明确“必须真实落盘”。
- 流程覆盖：经验摄入、反思触发、提案生成、治理审批、SOUL 应用、变更日志、状态更新、通知与管道报告。

### 4.2 配置驱动
- `evoclaw/config.json` 里关键开关：
  - `governance.level = autonomous`
  - `reflection.notable_batch_size = 2`
  - `sources.conversation.enabled = true`
  - `sources.rss.enabled = true`（GitHub Trending RSS）
  - `sources.x / moltbook` 默认关闭（待 API key）

### 4.3 执行器角色
- `evoclaw/cron_runner.py` 负责完整学习流，当前已按“**被动学习覆盖任务级事件 + 对话信号**”口径执行，不再仅限对话来源。
- `evoclaw/run.py heartbeat` 会依次调用 passive learning、active learning、governance 统计输出。

---

## 5. 钩子与反馈机制

- `evoclaw/hooks.py` 是统一 hook 入口，实际实现委托到 `feedback_system`。
- 公开接口包括：`before_task / before_subtask / after_subtask / after_task / governance_gate / handle_user_confirmation_reply`。

**机制价值：**
- 对外暴露稳定 API，内部可替换实现
- 任务生命周期点可插入审计、确认、治理控制

---

## 6. 当前机制的边界与注意点

1. **文档口径已收敛（本轮已修正）**
   - 已在 `evoclaw/README.md` 增加 DB-first 运行态声明，并将旧目录口径明确标注为“兼容目录（非主通道）”
   - 与根 `README.md`、`MEMORY.md` 的 DB-first 口径保持一致，降低新人误读风险

2. **数据查询需按最新 schema 字段**
   - 例如 `experiences` 无 `timestamp/category/summary` 字段，实际是 `created_at/type/content/...`
   - 旧脚本若按旧字段查，会直接报 SQL 错

3. **治理虽为 autonomous，仍需关注 proposal 审批策略透明度**
   - 自动应用能提速，但应配合清晰日志与可回滚路径

---

## 7. 建议的最小巡检命令

```bash
python3 evoclaw/validators/run_all.py
python3 evoclaw/validators/validate_experience.py memory/memory.db --config evoclaw/config.json --date $(date +%F)
python3 evoclaw/validators/check_pipeline_ran.py memory --since-minutes 30
sqlite3 memory/memory.db '.schema experiences'
sqlite3 memory/memory.db 'select created_at,type,substr(content,1,120) from experiences order by created_at desc limit 10;'
```

这些命令可快速确认：契约有效、经验写入正常、pipeline 在跑、schema 没漂移。


---

## 8. 统一消息处理与任务总结机制（新增）

- 当前机制按“统一消息处理”执行：不再按简单/复杂消息分叉到不同路径，消息统一进入任务流程，并经过四钩子闭环。
- 每次任务完成后会生成结构化任务总结并落入 `task_runs`（SQLite 表），包含：
  - 任务操作对象（task_id/task_type/task_name）
  - 使用技能与方法（skills/methods）
  - 过程步骤（execution_steps）
  - 最终输出与消息（output_summary/final_message）
  - 思考痕迹（thinking）
- 回复侧会附带“满意 / 不满意”反馈按钮，默认满意（未点击视为满意）。
- 若用户点击“不满意”，系统会：
  1) 将该任务在 `task_runs` 标记为 `unsatisfied + notable`
  2) 写入 notable 经验
  3) 立即触发 reflection 记录并生成高优先级改进 proposal

该机制实现了“任务执行 → 反馈确认 → notable 触发反思提案”的闭环。
- 学习策略分两条：
  1) **即时链路**：用户点“不满意”→ 立即标记 notable 并触发反思/提案
  2) **定时链路**：Cron 只从 `task_runs` 中提取“剩余任务”经验进行批量学习
- 对话文本不再作为定时被动学习主数据源；对话价值主要由任务总结中的 `thinking/final_message` 与即时不满意反馈承载。

