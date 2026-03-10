# Pattern A Compliance

This skill is **Pattern A Compliant** — the gold standard for OpenClaw skills.

## What Pattern A Means

| Requirement | Status | Description |
|-------------|--------|-------------|
| `docs/` | ✅ Required | User-facing documentation (README, examples, reference) |
| `src/` | ✅ Required | Modular source code with clear separation of concerns |
| `tests/` | ✅ Required | Comprehensive test suite (20+ tests minimum) |
| CLI | ✅ Required | Command-line interface for direct usage |
| SKILL.md | ✅ Required | Standardized skill metadata and documentation |

## Compliance Badge

```markdown
[![Pattern A](https://img.shields.io/badge/Pattern-A-success)](PATTERN_A.md)
```

## Why Pattern A Matters

1. **Maintainability** — Modular structure makes updates and fixes easier
2. **Testability** — Comprehensive tests prevent regressions
3. **Usability** — Full documentation enables self-service usage
4. **Portability** — Standard structure allows installation on any OpenClaw instance

## Verification

To verify this skill's compliance:

```bash
# Run the test suite
python -m pytest tests/

# Check structure
ls -la docs/ src/ tests/

# Verify SKILL.md exists
cat SKILL.md
```

## Migration Path

If you have a skill that needs to reach Pattern A compliance, see the [Skill Architecture Migration Runbook](https://github.com/hiveminderbot/stigmergic-system/blob/main/skills/.conventions/MIGRATION.md).

---
*This skill was validated as Pattern A compliant by automated assessment.*
