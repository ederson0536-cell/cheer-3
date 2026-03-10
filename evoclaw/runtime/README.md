# Runtime Contracts (Executable Artifacts)

Core contracts:
- `../OPERATIONS_MANUAL.md` (落地执行手册)
- `contracts/task_subtask.schema.json`
- `contracts/skill_registry.schema.json`
- `contracts/memory_contract.yaml`
- `contracts/proposal_pipeline.schema.json`
- `contracts/decision_trace.schema.json`
- `contracts/canonical_field_dictionary.yaml`
- `contracts/expectations/failure_injection_expectations.json`
- `contracts/service/persistence_boundary.yaml`

Regression suites:
- Golden: `examples/golden/`
- Dirty inputs: `examples/dirty/`

Validators and runs:
- `evoclaw/validators/validate_runtime_contracts.py`
- `evoclaw/validators/test_runtime_loops.py`
- `evoclaw/validators/test_real_sample_package.py`
- `evoclaw/validators/generate_regression_report.py`
- `evoclaw/validators/staging_trial_run.py`

## Quick checks

```bash
python3 evoclaw/validators/validate_runtime_contracts.py
python3 evoclaw/runtime/routing_score.py evoclaw/runtime/examples/skill_registry.example.json evoclaw/runtime/examples/routing_weights.example.json evoclaw/runtime/examples/decision_trace.from_routing.json
python3 evoclaw/validators/test_runtime_loops.py
python3 evoclaw/validators/test_real_sample_package.py
python3 evoclaw/validators/generate_regression_report.py
python3 evoclaw/validators/staging_trial_run.py
```

## Generated outputs

- `examples/decision_trace.loop_test.json`
- `examples/baseline.layered_dashboard.json`
- `examples/decision_trace.real_sample.json`
- `examples/regression_report.json`
- `examples/staging_trial_report.json`
