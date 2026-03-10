# MEMORY.md - 富贵's Long-Term Memory

> Last updated: 2026-03-08

---

## Identity

- **Name:** 富贵 (Fugui)
- **Type:** AI 助手，电子小精灵 🐲
- **Human:** 靓仔 (trump)
- **Platform:** Telegram

---

## System

- **Framework:** OpenClaw + EvoClaw
- **Governance:** autonomous (自动进化 + 通知)
- **Heartbeat:** 5 minutes (via Cron)
- **Skills:** 核心技能 + 候选技能

---

## Key Preferences

- 中文沟通
- 简洁明了
- 有话直说，不来虚的

---

## Memory Directory Index (`memory/`)

> 详细职责与改动触发规则见：`memory/README.md`

| 目录 | 用途 |
|------|------|
| `YYYY-MM-DD.md` | 每日日志 |
| `experiences/` | 经验记录 (JSONL) |
| `significant/` | 重要经验 |
| `reflections/` | 反思记录 |
| `proposals/` | 提案 (pending/approved/published) |
| `evoclaw-state.json` | 系统状态 |
| `soul_changes.jsonl` | SOUL 变更日志 |
| `feedback/` | 钩子触发日志 |
| `buffer/` | 工作缓冲区 |
| `episodic/` | 情景记忆 |
| `semantic/` | 语义记忆 |
| `graph/` | 知识图谱 |
| `candidate/` | 待定知识 |
| `rules/` | 规则库 |
| `wal/` | 决策日志 |
| `skill_performance/` | 技能表现 |
| `tasks/` | 任务历史 |
| `subtasks/` | 子任务 |
| `governance/` | 治理记录 |
| `recovery/` | 恢复日志 |
| `pipeline/` | 管道日志 |
| `failures.jsonl` | 失败记录 |
| `working/` | 工作目录 |

---

## Recent Events

- 2026-03-08: P0-P2 系统修复完成，消息钩子启用
- 2026-03-07: 系统搭建完成，EvoClaw 部署就绪

---

## Todo

- [ ] 连接 Moltbook (等 API Key)
- [ ] 连接 Twitter (等 API Key)
