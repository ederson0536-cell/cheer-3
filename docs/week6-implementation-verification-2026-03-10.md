# Week6 落实与验证报告（Execution Plan v1.1）

## 已落实项

1. 回归规则冻结（regression_rules v1）
   - 新增 `evoclaw/runtime/contracts/regression_rules.yaml`。
   - 固化 `pass / warning / fail` 判定门与发布动作标签。
2. 回归报告接入 Release Gate
   - 增强 `generate_regression_report.py`：
     - 覆盖 golden + dirty + real_sample + staging 结果聚合；
     - 根据 `regression_rules.yaml` 输出 `release_gate.status/action/policy_version`。
3. Staging + Canary + Rollback 演练验证
   - 新增 `validate_week6_release_gate.py`：
     - 执行 `staging_trial_run` 与 `generate_regression_report`；
     - 校验 release gate 结果存在；
     - 执行 governance quorum 批准、canary、publish、rollback 演练；
     - 校验 rollback 恢复时延 ≤ 300s。
4. 文档与运行入口收口
   - `evoclaw/runtime/README.md` 增加 `regression_rules.yaml` 与 Week6 验证命令。

## 验证命令

- `python3 evoclaw/validators/staging_trial_run.py`
- `python3 evoclaw/validators/generate_regression_report.py`
- `python3 evoclaw/validators/validate_week6_release_gate.py`
- `python3 evoclaw/validators/validate_canonical_alignment.py`
- `python3 evoclaw/validators/validate_state_transitions.py`
- `python3 evoclaw/validators/validate_week2_ingress_continuity.py`
- `python3 evoclaw/validators/validate_week3_runtime_gates.py`
- `python3 evoclaw/validators/validate_week4_memory_proposal.py`
- `python3 evoclaw/validators/validate_week5_file_governance.py`
- `python3 -m py_compile evoclaw/validators/generate_regression_report.py evoclaw/validators/validate_week6_release_gate.py`

## 结论

Week6 目标“回归与发布收口”已完成最小可运行版本：
- regression 规则已冻结并版本化；
- regression 报告可给出 pass/warning/fail 与 release_gate 动作；
- canary+rollback 演练可自动执行并验证时延约束；
- 可作为发布门前置检查。
