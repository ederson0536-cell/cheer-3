# Task P6: Validator A/B
**Person:** 6  
**Module:** Validator  
**File:** `src/validator/abtest.ts`

## Goal
A/B test original vs optimized skill to verify correctness.

## Deliverable
Runner that executes both versions and compares outputs.

```typescript
interface Validator {
  // Runs both versions with same inputs, compares outputs
  validate(skillId: string, optimizedSkill: OptimizedSkill): Promise<ValidationResult>;
  
  // Checks if outputs are semantically equivalent
  compareOutputs(original: any, optimized: any): boolean;
}

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

## Implementation Hints

```typescript
// src/validator/abtest.ts
import { Profiler } from '../profiler/core';
import { ProfilerDB } from '../profiler/db';

export class Validator {
  private profiler: Profiler;
  private db: ProfilerDB;
  
  constructor(dbPath: string) {
    this.profiler = new Profiler(dbPath);
    this.db = new ProfilerDB(dbPath);
  }
  
  async validate(
    skillId: string, 
    optimizedSkill: OptimizedSkill
  ): Promise<ValidationResult> {
    
    // 1. Generate test inputs (simplified: use hardcoded examples)
    const testInputs = this.generateTestInputs(skillId);
    
    // 2. Run original version
    const originalResults = await this.runVersion(
      skillId, 
      optimizedSkill.originalVersion, 
      testInputs
    );
    
    // 3. Run optimized version
    const optimizedResults = await this.runVersion(
      skillId, 
      optimizedSkill.optimizedVersion, 
      testInputs
    );
    
    // 4. Compare outputs
    const outputsMatch = this.compareOutputs(
      originalResults.outputs, 
      optimizedResults.outputs
    );
    
    // 5. Calculate improvement
    const improvement = this.calculateImprovement(
      originalResults.metrics,
      optimizedResults.metrics
    );
    
    return {
      skillId,
      originalOutput: originalResults.outputs,
      optimizedOutput: optimizedResults.outputs,
      outputsMatch,
      originalMetrics: originalResults.metrics,
      optimizedMetrics: optimizedResults.metrics,
      improvement,
      approved: outputsMatch && improvement > 0.1 // 10% improvement threshold
    };
  }
  
  private async runVersion(
    skillId: string,
    code: string,
    inputs: any[]
  ): Promise<{ outputs: any[], metrics: SkillMetrics }> {
    // In real implementation, would sandbox and execute
    // For MVP, return simulated results
    
    const start = Date.now();
    const outputs: any[] = [];
    
    for (const input of inputs) {
      // Simulated execution
      outputs.push({ result: 'mock', input });
    }
    
    return {
      outputs,
      metrics: {
        skillId,
        executionMs: Date.now() - start,
        tokensIn: 500,
        tokensOut: 300,
        success: true,
        timestamp: Date.now()
      }
    };
  }
  
  compareOutputs(original: any, optimized: any): boolean {
    // Deep equality check
    return JSON.stringify(original) === JSON.stringify(optimized);
  }
  
  private generateTestInputs(skillId: string): any[] {
    // Return domain-specific test cases
    const defaultInputs = [
      { test: 'basic' },
      { test: 'edge_case' },
      { test: 'large_input' }
    ];
    
    return defaultInputs;
  }
  
  private calculateImprovement(
    original: SkillMetrics,
    optimized: SkillMetrics
  ): number {
    const tokenImprovement = 1 - (optimized.tokensOut / original.tokensOut);
    const speedImprovement = 1 - (optimized.executionMs / original.executionMs);
    
    // Weighted average
    return (tokenImprovement * 0.6) + (speedImprovement * 0.4);
  }
}
```

## Success Check
```bash
# Should run A/B test and report if optimization is valid
npm run validate -- --skill=time-tracker
# Output: 
# ✅ Outputs match: true
# ⚡ Improvement: 25%
# 🟢 APPROVED for promotion
```

## Integration
Uses P1 profiler, consumes P5's optimized skill, feeds into P7 promotion decision.

## Time Budget
15-20 minutes
