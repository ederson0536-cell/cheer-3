# OpenClaw / EvoClaw Workspace Guide

本仓库是 OpenClaw 主工作区，包含两套并行内容：

- 根目录 Agent 身份与会话文件（`SOUL.md` / `USER.md` / `AGENTS.md` 等）
- `evoclaw/` 下的 EvoClaw 运行时契约、验证器、样本集与运行手册

> 如果你要快速上手，请先读：
> 1) `evoclaw/configure.md`
> 2) `evoclaw/SKILL.md`
> 3) `evoclaw/OPERATIONS_MANUAL.md`

---

## 1) 根目录结构（按官方文档整理）

```text
.
├── AGENTS.md
├── HEARTBEAT.md
├── IDENTITY.md
├── SOUL.md
├── SYSTEM_FRAMEWORK_PROPOSAL.md
├── TOOLS.md
├── USER.md
├── README.md
├── skills/
│   ├── seo-kit/
│   └── self-learning-skills/
└── evoclaw/
    ├── README.md
    ├── SKILL.md
    ├── configure.md
    ├── OPERATIONS_MANUAL.md
    ├── config.json
    ├── runtime/
    │   ├── README.md
    │   ├── contracts/
    │   ├── examples/
    │   └── routing_score.py
    └── validators/
```

---

## 2) 关键文档职责

- `SYSTEM_FRAMEWORK_PROPOSAL.md`：v3 系统框架总设计（控制面/数据面/治理门/演进流程）
- `evoclaw/OPERATIONS_MANUAL.md`：落地运行手册（实施步骤、节奏、巡检）
- `evoclaw/runtime/README.md`：契约与验证脚本的快速命令入口
- `evoclaw/runtime/contracts/`：机器可校验契约（schema / policy / boundary）
- `evoclaw/runtime/examples/`：黄金样本、脏输入样本、决策 trace、回归结果
- `evoclaw/validators/`：闭环测试、回归报告、staging 试跑脚本

---

## 3) 最小可执行流程（本地）

```bash
python3 evoclaw/validators/validate_runtime_contracts.py
python3 evoclaw/validators/test_runtime_loops.py
python3 evoclaw/validators/test_real_sample_package.py
python3 evoclaw/validators/generate_regression_report.py
python3 evoclaw/validators/staging_trial_run.py
```

预期产物在 `evoclaw/runtime/examples/`：

- `decision_trace.loop_test.json`
- `decision_trace.real_sample.json`
- `baseline.layered_dashboard.json`
- `regression_report.json`
- `staging_trial_report.json`

---

## 4) 定时任务建议（实施保障）

建议先在 **staging** 跑定时，再逐步迁移到 prod：

- 每 30 分钟：`test_runtime_loops.py`（闭环 + failure injection）
- 每 2 小时：`generate_regression_report.py`（回归结果）
- 每天 1 次：`staging_trial_run.py`（低风险真实样本）

可参考：`evoclaw/runtime/examples/cron.schedule.example`

---

## 5) 实施边界与持久化

持久服务边界定义见：

- `evoclaw/runtime/contracts/service/persistence_boundary.yaml`

建议上线前至少确认四个接口职责：

- 调度入口（scheduler entry）
- 状态存储（state store）
- trace 落盘（decision trace sink）
- proposal review 队列（review queue）

---

## 6) 目录维护原则

- 优先复用既有目录，不新增“临时散落目录”
- 所有新增契约放 `evoclaw/runtime/contracts/`
- 所有新增样本放 `evoclaw/runtime/examples/` 并更新 manifest
- 所有验证脚本放 `evoclaw/validators/`

这样可以保证：设计、契约、样本、验证、报告处于同一条可审计链路。
