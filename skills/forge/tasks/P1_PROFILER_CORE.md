# Task P1: Profiler Core
**Person:** 1  
**Module:** Profiler  
**File:** `src/profiler/core.ts`

## Goal
Capture execution metrics every time a skill runs.

## Deliverable
A TypeScript module that wraps skill execution and records metrics.

```typescript
interface Profiler {
  // Wraps a skill execution and records metrics
  profile<T>(skillId: string, fn: () => Promise<T>): Promise<T>;
  
  // Returns raw metrics for a skill
  getMetrics(skillId: string): SkillMetrics[];
}
```

## Implementation Hints

```typescript
// src/profiler/core.ts
import { Database } from './db';

export class Profiler {
  private db: Database;
  
  constructor(dbPath: string) {
    this.db = new Database(dbPath);
  }
  
  async profile<T>(skillId: string, fn: () => Promise<T>): Promise<T> {
    const start = Date.now();
    const startTokens = this.estimateTokens(); // approximate
    
    try {
      const result = await fn();
      const executionMs = Date.now() - start;
      const tokensOut = this.estimateOutput(result);
      
      this.db.insert({
        skillId,
        executionMs,
        tokensIn: startTokens,
        tokensOut,
        success: true,
        timestamp: Date.now()
      });
      
      return result;
    } catch (error) {
      this.db.insert({
        skillId,
        executionMs: Date.now() - start,
        tokensIn: startTokens,
        tokensOut: 0,
        success: false,
        timestamp: Date.now()
      });
      throw error;
    }
  }
  
  private estimateTokens(): number {
    // Simple heuristic: ~4 chars per token
    return 500; // placeholder
  }
  
  private estimateOutput(result: any): number {
    return JSON.stringify(result).length / 4;
  }
}
```

## Success Check
```bash
# Should track 5 executions and store in SQLite
npm run profile -- --skill=time-tracker --iterations=5
```

## Integration
Works with P2 (database) and P7 (orchestrator).

## Time Budget
10-15 minutes
