# Task P3: Analyzer Engine
**Person:** 3  
**Module:** Analyzer  
**File:** `src/analyzer/engine.ts`

## Goal
Identify skills that need optimization based on performance data.

## Deliverable
Engine that queries metrics and flags optimization candidates.

```typescript
interface Analyzer {
  // Returns skills that should be optimized
  findCandidates(): OptimizationCandidate[];
  
  // Prioritizes by impact
  prioritize(candidates: OptimizationCandidate[]): OptimizationCandidate[];
}

interface OptimizationCandidate {
  skillId: string;
  avgExecutionMs: number;
  avgTokens: number;
  failureRate: number;
  priority: 'high' | 'medium' | 'low';
  reason: string;
}
```

## Implementation Hints

```typescript
// src/analyzer/engine.ts
import { ProfilerDB } from '../profiler/db';

export class Analyzer {
  private db: ProfilerDB;
  
  // Thresholds for flagging
  private readonly SLOW_THRESHOLD_MS = 2000;
  private readonly HIGH_TOKEN_THRESHOLD = 2000;
  private readonly HIGH_FAILURE_RATE = 0.2;
  
  constructor(dbPath: string) {
    this.db = new ProfilerDB(dbPath);
  }
  
  findCandidates(): OptimizationCandidate[] {
    const skills = this.db.getAllSkills();
    const candidates: OptimizationCandidate[] = [];
    
    for (const skillId of skills) {
      const metrics = this.db.getAverageMetrics(skillId);
      
      const issues: string[] = [];
      if (metrics.avgExecutionMs > this.SLOW_THRESHOLD_MS) {
        issues.push(`Slow: ${metrics.avgExecutionMs}ms avg`);
      }
      if (metrics.avgTokens > this.HIGH_TOKEN_THRESHOLD) {
        issues.push(`Token heavy: ${metrics.avgTokens} avg`);
      }
      if (metrics.failureRate > this.HIGH_FAILURE_RATE) {
        issues.push(`Unstable: ${(metrics.failureRate * 100).toFixed(1)}% fail rate`);
      }
      
      if (issues.length > 0) {
        candidates.push({
          skillId,
          avgExecutionMs: metrics.avgExecutionMs,
          avgTokens: metrics.avgTokens,
          failureRate: metrics.failureRate,
          priority: this.calculatePriority(metrics),
          reason: issues.join('; ')
        });
      }
    }
    
    return this.prioritize(candidates);
  }
  
  private calculatePriority(m: AggregatedMetrics): 'high' | 'medium' | 'low' {
    const score = (m.avgExecutionMs / 1000) + (m.avgTokens / 500) + (m.failureRate * 10);
    if (score > 5) return 'high';
    if (score > 2) return 'medium';
    return 'low';
  }
  
  prioritize(candidates: OptimizationCandidate[]): OptimizationCandidate[] {
    return candidates.sort((a, b) => {
      const priorityOrder = { high: 3, medium: 2, low: 1 };
      return priorityOrder[b.priority] - priorityOrder[a.priority];
    });
  }
}
```

## Success Check
```bash
# Should output ranked list of skills to optimize
npm run analyze
# Output example:
# [HIGH] time-tracker: Slow: 3500ms avg; Token heavy: 2100 avg
# [MED] web-search: Token heavy: 1800 avg
```

## Integration
Uses P2's database, feeds into P4-5 optimizer.

## Time Budget
10-15 minutes
