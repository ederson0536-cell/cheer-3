# Task P2: Profiler Database
**Person:** 2  
**Module:** Profiler  
**File:** `src/profiler/db.ts`

## Goal
SQLite storage for skill execution metrics.

## Deliverable
Database wrapper with CRUD operations.

```typescript
interface Database {
  insert(metric: SkillMetrics): void;
  getMetrics(skillId: string): SkillMetrics[];
  getAllSkills(): string[];
  getAverageMetrics(skillId: string): AggregatedMetrics;
}

interface AggregatedMetrics {
  skillId: string;
  avgExecutionMs: number;
  avgTokens: number;
  totalRuns: number;
  failureRate: number;
}
```

## Implementation Hints

```typescript
// src/profiler/db.ts
import Database from 'better-sqlite3';

export class ProfilerDB {
  private db: Database.Database;
  
  constructor(dbPath: string = './skill-forge.db') {
    this.db = new Database(dbPath);
    this.init();
  }
  
  private init() {
    this.db.exec(`
      CREATE TABLE IF NOT EXISTS skill_metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        skill_id TEXT NOT NULL,
        execution_ms INTEGER NOT NULL,
        tokens_in INTEGER NOT NULL,
        tokens_out INTEGER NOT NULL,
        success BOOLEAN NOT NULL,
        timestamp INTEGER NOT NULL
      );
      
      CREATE INDEX IF NOT EXISTS idx_skill_id ON skill_metrics(skill_id);
      CREATE INDEX IF NOT EXISTS idx_timestamp ON skill_metrics(timestamp);
    `);
  }
  
  insert(metric: SkillMetrics): void {
    const stmt = this.db.prepare(`
      INSERT INTO skill_metrics 
      (skill_id, execution_ms, tokens_in, tokens_out, success, timestamp)
      VALUES (?, ?, ?, ?, ?, ?)
    `);
    
    stmt.run(
      metric.skillId,
      metric.executionMs,
      metric.tokensIn,
      metric.tokensOut,
      metric.success ? 1 : 0,
      metric.timestamp
    );
  }
  
  getAverageMetrics(skillId: string): AggregatedMetrics {
    const stmt = this.db.prepare(`
      SELECT 
        AVG(execution_ms) as avgExecutionMs,
        AVG(tokens_in + tokens_out) as avgTokens,
        COUNT(*) as totalRuns,
        SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) * 1.0 / COUNT(*) as failureRate
      FROM skill_metrics
      WHERE skill_id = ?
    `);
    
    return stmt.get(skillId);
  }
}
```

## Success Check
```bash
# Should create database and store metrics
npm run profile
# Check: sqlite3 skill-forge.db "SELECT * FROM skill_metrics;"
```

## Integration
Works with P1 (profiler core) and P3 (analyzer).

## Time Budget
10-15 minutes
