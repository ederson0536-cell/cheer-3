# Forge

Self-optimizing skill system for OpenClaw agents. Tracks performance, detects inefficiencies, and auto-generates improved versions.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                     FORGE v0.1                         │
├─────────────────────────────────────────────────────────────┤
│  ┌──────────┐    ┌──────────┐    ┌──────────┐              │
│  │ PROFILER │───▶│ ANALYZER │───▶│ OPTIMIZER│              │
│  │  (P1-2)  │    │   (P3)   │    │  (P4-5)  │              │
│  └──────────┘    └──────────┘    └────┬─────┘              │
│       ▲                                 │                    │
│       │                                 ▼                    │
│       │                          ┌──────────┐              │
│       │                          │VALIDATOR │              │
│       │                          │   (P6)   │              │
│       │                          └────┬─────┘              │
│       │                               │                    │
│       └───────────────────────────────┘                    │
│                                       ▼                    │
│                              ┌──────────────┐             │
│                              │ FORGE CORE   │             │
│                              │    (P7)      │             │
│                              └──────────────┘             │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

```bash
# 1. Clone and setup
git clone https://github.com/minicarlo/forge.git
cd forge
npm install

# 2. Run profiler (captures metrics)
npm run profile

# 3. Run analyzer (finds slow skills)
npm run analyze

# 4. Run optimizer (generates v2)
npm run optimize --skill=time-tracker

# 5. Run validator (A/B test)
npm run validate --skill=time-tracker
```

## Team Tasks (Parallel Work)

| Person | Module | File | Status |
|--------|--------|------|--------|
| 1 | Profiler Core | `src/profiler/core.ts` | 🔴 Not started |
| 2 | Profiler Storage | `src/profiler/db.ts` | 🔴 Not started |
| 3 | Analyzer Engine | `src/analyzer/engine.ts` | 🔴 Not started |
| 4 | Optimizer Prompts | `src/optimizer/prompts.ts` | 🔴 Not started |
| 5 | Optimizer Runner | `src/optimizer/runner.ts` | 🔴 Not started |
| 6 | Validator A/B | `src/validator/abtest.ts` | 🔴 Not started |
| 7 (Carlo) | Forge Core | `src/core/orchestrator.ts` | 🔴 Not started |

## Integration Points

Each module exposes a standard interface:

```typescript
// Profiler ──▶ returns metrics
interface SkillMetrics {
  skillId: string;
  executionMs: number;
  tokensIn: number;
  tokensOut: number;
  success: boolean;
  timestamp: number;
}

// Analyzer ──▶ returns optimization candidates
interface OptimizationCandidate {
  skillId: string;
  avgExecutionMs: number;
  avgTokens: number;
  failureRate: number;
  priority: 'high' | 'medium' | 'low';
}

// Optimizer ──▶ returns new skill version
interface OptimizedSkill {
  skillId: string;
  originalVersion: string;
  optimizedVersion: string;
  changes: string[];
  estimatedImprovement: number;
}

// Validator ──▶ returns comparison result
interface ValidationResult {
  skillId: string;
  originalOutput: any;
  optimizedOutput: any;
  outputsMatch: boolean;
  originalMetrics: SkillMetrics;
  optimizedMetrics: SkillMetrics;
  improvement: number;
  approved: boolean;
}
```

## Success Criteria (1 Hour)

- [ ] Profiler tracks at least 3 metrics
- [ ] Analyzer flags at least 1 slow skill
- [ ] Optimizer generates 1 improved version
- [ ] Validator confirms outputs match
- [ ] Manual promotion works

## License
MIT
