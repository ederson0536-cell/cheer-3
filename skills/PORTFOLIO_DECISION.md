# Skills Portfolio Decision (v1)

> 目标：回答“哪些技能需要保留，哪些技能可以删除”，并与 `SYSTEM_FRAMEWORK_PROPOSAL.md` 的治理思路一致。

## 0) 当前执行状态（2026-03-06）

以下目录已从仓库删除（按第 4 节建议执行）：

- `skills/self-learning-skills`
- `skills/self-evolution-skill`
- `skills/daily-self-reflection`
- `skills/memory-systems`
- `skills/knowledge-graph-v3`

---

## 1) 决策标准（先统一口径）

按四个维度做分层，不直接按“喜欢/不喜欢”删：

- **对当前 Runtime 的直接价值**：是否直接服务 Task/Subtask、Routing、Memory、Proposal 闭环。
- **重复度**：是否与同类技能功能重叠（尤其是 memory/self-learning 类）。
- **维护成本**：体量是否过大、依赖是否复杂、是否引入额外服务。
- **治理可控性**：是否容易纳入 trust level / canary / rollback 管控。

## 2) 建议“保留”的技能（核心生产集）

这些建议保留并继续维护：

1. `openclaw-skill-anti-repeat-errors`
   - 与失败分型、重复错误抑制、proposal 改进方向直接一致。
2. `self-learning-skill`
   - 具备脚本、配置、测试，作为“持续学习”主实现保留。
3. `valence-openclaw`
   - 作为 OpenClaw 插件化与 session hooks 的桥接能力保留。
4. `zh-knowledge-manager`
   - 可作为知识沉淀/中文场景增强能力保留（建议后续治理分级）。

## 3) 建议“保留但降级为候选/实验”的技能

这些可以保留源码，但不进入默认生产路由：

- `DeepRecall`
- `obsidian-openclaw-memory`
- `novyx-memory-skill`
- `Nemp-memory`
- `MemOS`
- `OpenViking`
- `ClawRoam`

原因：价值可能存在，但与现有 memory/routing 路线重叠较多或引入成本较高，适合放在 canary / 实验池。

## 4) 建议“可删除或归档”的技能

优先删除“重复且低集成价值”的技能，先归档再删：

- `self-learning-skills`（与 `self-learning-skill` 重复，保留后者即可）
- `self-evolution-skill`（与 EvoClaw 主线职责重叠）
- `daily-self-reflection`（可被主流程吸收）
- `memory-systems`（概念集合型，非核心运行件）
- `knowledge-graph-v3`（若未接入当前 contract/validator，可先归档）

> 注意：删除前先打标签并保留快照（zip/tag），避免未来回滚无源。

## 5) 高体量目录清理优先级（成本视角）

按目录体积看，建议优先审查以下高成本项（若未进入生产路径可先归档）：

- `dojo.md` (~164M)
- `forge` (~75M)
- `mindkeeper` (~65M)
- `OpenViking` (~26M)
- `Nemp-memory` / `MemOS` / `zh-knowledge-manager`（~16M 级）

## 6) 执行顺序（安全落地）

1. 先确定 **生产白名单**（第 2 节）。
2. 第 3 节目录迁移到 `skills/_candidate/`（或冻结在路由层）。
3. 第 4 节目录先归档（tag + 压缩），观察 2 周无依赖后再删除。
4. 每次删减后运行：
   - `python3 evoclaw/validators/validate_runtime_contracts.py`
   - `python3 evoclaw/validators/test_runtime_loops.py`
   - `python3 evoclaw/validators/generate_regression_report.py`

## 7) 一句话结论

**保留少量可治理的核心技能，把重复 memory/learning 技能降级为候选或归档，才能让 Runtime 按稳定基线演进而不是技能集合失控。**
