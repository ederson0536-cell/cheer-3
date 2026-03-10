# TOOLS.md - Local Tool Ops Notes

Skills define _how_ tools work. This file records this workspace's **local tool facts** so runtime knows what each tool is for and when to update these notes.

## File Purpose & Update Trigger

- **Purpose:** Keep environment-specific tool metadata (paths, versions, aliases, preferred defaults) out of shared skill code.
- **Update when:**
  - tool path/version changed,
  - login/auth method changed,
  - default execution habits changed,
  - local infra endpoint/alias changed.

## What Goes Here

- Camera names and locations
- SSH hosts and aliases
- Preferred voices for TTS
- Speaker/room names
- Device nicknames
- Anything environment-specific

## Operational Rules

- Keep entries concise and actionable.
- Never store secrets in plaintext (tokens/passwords/private keys).
- If a tool setting impacts runtime behavior, sync summary into relevant docs/config.

## Examples

```markdown
### Cameras

- living-room → Main area, 180° wide angle
- front-door → Entrance, motion-triggered

### SSH

- home-server → 192.168.1.100, user: admin

### TTS

- Preferred voice: "Nova" (warm, slightly British)
- Default speaker: Kitchen HomePod
```

## Codex

- **路径**: `~/.npm-global/bin/codex`
- **版本**: 0.106.0
- **登录**: 已使用 ChatGPT 订阅登录
- **用法**: `codex exec "任务描述"`
