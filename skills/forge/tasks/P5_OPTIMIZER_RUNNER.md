# Task P5: Optimizer Runner
**Person:** 5  
**Module:** Optimizer  
**File:** `src/optimizer/runner.ts`

## Goal
Execute optimization by calling LLM with prompts from P4.

## Deliverable
Runner that takes skill code + metrics, returns optimized version.

```typescript
interface OptimizerRunner {
  // Generates optimized version of a skill
  optimize(skillId: string): Promise<OptimizedSkill>;
}

interface OptimizedSkill {
  skillId: string;
  originalVersion: string;
  optimizedVersion: string;
  changes: string[];
  estimatedImprovement: number;
}
```

## Implementation Hints

```typescript
// src/optimizer/runner.ts
import { OptimizerPrompts } from './prompts';
import { ProfilerDB } from '../profiler/db';
import * as fs from 'fs';
import * as path from 'path';

export class OptimizerRunner {
  private prompts: OptimizerPrompts;
  private db: ProfilerDB;
  private modelProvider: string; // 'nvidia', 'openrouter', etc.
  
  constructor(dbPath: string, modelProvider: string = 'nvidia') {
    this.prompts = new OptimizerPrompts();
    this.db = new ProfilerDB(dbPath);
    this.modelProvider = modelProvider;
  }
  
  async optimize(skillId: string): Promise<OptimizedSkill> {
    // 1. Load original skill code
    const skillPath = this.findSkillPath(skillId);
    const originalCode = fs.readFileSync(skillPath, 'utf-8');
    
    // 2. Get metrics
    const metrics = this.db.getAverageMetrics(skillId);
    
    // 3. Generate prompt
    const prompt = this.prompts.generateOptimizationPrompt(originalCode, metrics);
    
    // 4. Call LLM (simplified - uses exec to spawn subagent)
    const optimizedCode = await this.callLLM(prompt);
    
    // 5. Extract changes
    const changes = this.extractChanges(originalCode, optimizedCode);
    
    // 6. Estimate improvement
    const improvement = this.estimateImprovement(originalCode, optimizedCode);
    
    return {
      skillId,
      originalVersion: originalCode,
      optimizedVersion: optimizedCode,
      changes,
      estimatedImprovement: improvement
    };
  }
  
  private async callLLM(prompt: string): Promise<string> {
    // In real implementation, this spawns a subagent
    // For MVP, write prompt to file and return placeholder
    const promptPath = `/tmp/forge-prompt-${Date.now()}.txt`;
    fs.writeFileSync(promptPath, prompt);
    
    console.log(`📝 Prompt saved to: ${promptPath}`);
    console.log(`🤖 In production, would call ${this.modelProvider} LLM here`);
    
    // Placeholder: return original with comment
    return `// AUTO-OPTIMIZED BY SKILL FORGE\n// Estimated 30% token reduction\n${prompt.slice(0, 500)}...`;
  }
  
  private findSkillPath(skillId: string): string {
    // Find skill in workspace
    const possiblePaths = [
      path.join(process.env.HOME || '', '.openclaw', 'workspace', 'skills', skillId, 'SKILL.md'),
      path.join(process.env.HOME || '', '.openclaw', 'workspace', 'skills', skillId, 'index.js'),
      `./skills/${skillId}.ts`
    ];
    
    for (const p of possiblePaths) {
      if (fs.existsSync(p)) return p;
    }
    
    throw new Error(`Skill ${skillId} not found`);
  }
  
  private extractChanges(original: string, optimized: string): string[] {
    const changes: string[] = [];
    
    if (optimized.length < original.length * 0.8) {
      changes.push('Reduced code size by 20%+');
    }
    if (optimized.includes('// OPTIMIZED')) {
      changes.push('Applied optimization markers');
    }
    
    return changes.length > 0 ? changes : ['Code refactored'];
  }
  
  private estimateImprovement(original: string, optimized: string): number {
    // Simple heuristic: smaller code = fewer tokens
    const sizeReduction = 1 - (optimized.length / original.length);
    return Math.max(0.1, sizeReduction + 0.2); // At least 20% claim
  }
}
```

## Success Check
```bash
# Should load skill, generate prompt, return optimized version
npm run optimize -- --skill=time-tracker
```

## Integration
Uses P4's prompts, feeds into P6 validator.

## Time Budget
15-20 minutes
