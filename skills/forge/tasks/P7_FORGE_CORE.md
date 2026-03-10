# Task P7: Forge Core (YOU)
**Person:** 7 (Carlo)  
**Module:** Core Orchestrator  
**File:** `src/core/orchestrator.ts`

## Goal
Wire everything together. The conductor of the orchestra.

## Deliverable
Main entry point that orchestrates the full optimization pipeline.

```typescript
interface ForgeOrchestrator {
  // Full pipeline: profile → analyze → optimize → validate → promote
  forge(skillId?: string): Promise<void>;
  
  // Individual steps
  profile(skillId: string): Promise<void>;
  analyze(): Promise<OptimizationCandidate[]>;
  optimize(skillId: string): Promise<OptimizedSkill>;
  validate(skill: OptimizedSkill): Promise<ValidationResult>;
  promote(skillId: string): void;
}
```

## Implementation Hints

```typescript
// src/core/orchestrator.ts
import { Profiler } from '../profiler/core';
import { Analyzer } from '../analyzer/engine';
import { OptimizerRunner } from '../optimizer/runner';
import { Validator } from '../validator/abtest';

export class ForgeOrchestrator {
  private profiler: Profiler;
  private analyzer: Analyzer;
  private optimizer: OptimizerRunner;
  private validator: Validator;
  private dbPath: string;
  
  constructor(dbPath: string = './skill-forge.db') {
    this.dbPath = dbPath;
    this.profiler = new Profiler(dbPath);
    this.analyzer = new Analyzer(dbPath);
    this.optimizer = new OptimizerRunner(dbPath);
    this.validator = new Validator(dbPath);
  }
  
  async forge(targetSkill?: string): Promise<void> {
    console.log('🔥 SKILL FORGE v0.1');
    console.log('====================\n');
    
    // STEP 1: Analyze (find candidates)
    console.log('📊 Step 1: Analyzing skills...');
    const candidates = await this.analyze();
    
    if (candidates.length === 0) {
      console.log('✅ All skills are optimized!');
      return;
    }
    
    console.log(`Found ${candidates.length} optimization candidates:\n`);
    candidates.forEach(c => {
      console.log(`  [${c.priority.toUpperCase()}] ${c.skillId}: ${c.reason}`);
    });
    
    // Select target (user-specified or highest priority)
    const skillId = targetSkill || candidates[0].skillId;
    console.log(`\n🎯 Targeting: ${skillId}\n`);
    
    // STEP 2: Optimize
    console.log('⚡ Step 2: Generating optimized version...');
    const optimized = await this.optimize(skillId);
    console.log(`   Generated version with ${optimized.estimatedImprovement * 100}% estimated improvement\n`);
    
    // STEP 3: Validate
    console.log('🧪 Step 3: Validating...');
    const validation = await this.validator.validate(skillId, optimized);
    
    console.log(`   Outputs match: ${validation.outputsMatch ? '✅' : '❌'}`);
    console.log(`   Token improvement: ${(validation.improvement * 100).toFixed(1)}%`);
    console.log(`   Approved: ${validation.approved ? '🟢 YES' : '🔴 NO'}\n`);
    
    // STEP 4: Promote (if approved)
    if (validation.approved) {
      console.log('🚀 Step 4: Promoting to production...');
      this.promote(skillId);
      console.log('   ✅ Done!');
    } else {
      console.log('   ⏭️  Skipping promotion (validation failed)');
    }
    
    console.log('\n====================');
    console.log('Forge complete! 🔥');
  }
  
  async profile(skillId: string): Promise<void> {
    // Delegate to P1-2
    console.log(`Profiling ${skillId}...`);
  }
  
  async analyze(): Promise<OptimizationCandidate[]> {
    // Delegate to P3
    return this.analyzer.findCandidates();
  }
  
  async optimize(skillId: string): Promise<OptimizedSkill> {
    // Delegate to P4-5
    return this.optimizer.optimize(skillId);
  }
  
  promote(skillId: string): void {
    // Move optimized version to active
    console.log(`Promoting ${skillId}`);
    // fs.writeFileSync(skillPath, optimizedCode);
  }
}

// CLI entry point
async function main() {
  const skillId = process.argv[2];
  const forge = new ForgeOrchestrator();
  await forge.forge(skillId);
}

main().catch(console.error);
```

## Your Job During the Build

1. **0-10 min:** Set up repo, ensure everyone can git push/pull
2. **10-30 min:** Help debug integration issues between modules
3. **30-50 min:** Wire together working modules, stub missing ones
4. **50-60 min:** Demo run: `npm run forge -- time-tracker`

## Critical Integration Points

Make sure these lines up:
```typescript
// P1 Profiler returns metrics that P3 expects
// P3 Analyzer outputs format P7 expects
// P5 Optimizer outputs format P6 expects
// P6 Validator returns approval boolean
```

## Emergency Fallback

If someone falls behind, stub their module:
```typescript
// Stub for missing module
class StubAnalyzer {
  findCandidates() {
    return [{ skillId: 'time-tracker', priority: 'high' }];
  }
}
```

## Time Budget
- Setup: 5 min
- Integration: 30 min
- Demo prep: 15 min
- Buffer: 10 min

**You've got this. 🔥**
