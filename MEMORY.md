# MEMORY.md - 富贵's Long-Term Memory

> Last updated: 2026-03-10

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
- **Memory Mode:** DB-first (`memory/memory.db` is canonical)

---

## Key Preferences

- 中文沟通
- 简洁明了
- 有话直说，不来虚的

---

## Memory Directory Index (`memory/`)

| 路径 | 用途 |
|------|------|
| `memory.db` | 运行时唯一主写源（经验/提案/反思/状态等） |
| `experiences/` | 历史/迁移用 JSONL 投影 |
| `proposals/` | 提案文件队列（兼容保留） |
| `reflections/` | 反思文件产物（兼容保留） |
| `evoclaw-state.json` | 状态快照 |

---

## Recent Events

- 2026-03-10: 完成 DB-first 改造，巡检与关键组件统一基于 `memory.db`。
- 2026-03-08: P0-P2 系统修复完成，消息钩子启用。

---

## Todo

- [ ] 清理 remaining JSONL 读取路径（仅保留迁移工具）
- [ ] 连接 Moltbook (等 API Key)
- [ ] 连接 Twitter (等 API Key)
