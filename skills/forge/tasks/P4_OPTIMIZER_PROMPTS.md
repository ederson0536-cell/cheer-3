# Task P4: Optimizer Prompts
**Person:** 4  
**Module:** Optimizer  
**File:** `src/optimizer/prompts.ts`

## Goal
Create prompts that generate improved skill code.

## Deliverable
Prompt templates for skill optimization.

```typescript
interface OptimizerPrompts {
  // Main optimization prompt
  generateOptimizationPrompt(skillCode: string, metrics: AggregatedMetrics): string;
  
  // Safety check prompt
  generateSafetyPrompt(original: string, optimized: string): string;
}
```

## Implementation Hints

```typescript
// src/optimizer/prompts.ts

export const OPTIMIZATION_PROMPT = `
You are an expert code optimizer. Your task is to optimize the provided skill code.

ORIGINAL CODE:
\`\`\`typescript
{skillCode}
\`\`\`

PERFORMANCE METRICS:
- Average execution time: {avgExecutionMs}ms
- Average tokens used: {avgTokens}
- Failure rate: {failureRate}%

OPTIMIZATION GOALS (in priority order):
1. Reduce token usage by 30%+ (fewer API calls, more efficient prompts)
2. Reduce execution time by 20%+
3. Maintain exact same functionality (outputs must be identical)
4. Improve error handling

RULES:
- Do NOT change function signatures
- Do NOT change output formats
- Do NOT remove safety checks
- DO add early returns where possible
- DO batch operations when possible
- DO use more efficient data structures

OUTPUT FORMAT:
Return ONLY the optimized code, wrapped in a code block.
Include a brief comment at the top explaining the key changes.
`;

export const SAFETY_PROMPT = `
Verify that these two code versions produce IDENTICAL outputs for all inputs.

ORIGINAL:
\`\`\`typescript
{original}
\`\`\`

OPTIMIZED:
\`\`\`typescript
{optimized}
\`\`\`

Check for:
1. Same return types
2. Same side effects
3. Same error handling
4. No behavioral changes

Respond with ONLY:
SAFE: <reason>
or
UNSAFE: <reason>
`;

export class OptimizerPrompts {
  generateOptimizationPrompt(skillCode: string, metrics: AggregatedMetrics): string {
    return OPTIMIZATION_PROMPT
      .replace('{skillCode}', skillCode)
      .replace('{avgExecutionMs}', metrics.avgExecutionMs.toString())
      .replace('{avgTokens}', metrics.avgTokens.toString())
      .replace('{failureRate}', (metrics.failureRate * 100).toFixed(1));
  }
  
  generateSafetyPrompt(original: string, optimized: string): string {
    return SAFETY_PROMPT
      .replace('{original}', original)
      .replace('{optimized}', optimized);
  }
}
```

## Success Check
```bash
# Should generate valid prompts with metrics injected
cat src/optimizer/prompts.ts
```

## Integration
Used by P5 (optimizer runner) to call LLM.

## Time Budget
10-15 minutes
