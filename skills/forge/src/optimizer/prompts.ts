import { AnalysisResult } from '../types';

/**
 * Generate LLM prompts for skill optimization.
 * These templates turn profiler data into precise rewrite instructions.
 */
export function buildOptimizationPrompt(
  skillContent: string,
  analysis: AnalysisResult
): string {
  const { metrics, reasons, score } = analysis;

  return `You are an expert at optimizing AI agent skills (prompt templates).

## Task
Rewrite the skill below to be more efficient. Your goals:
1. Reduce token count while preserving all functionality
2. Remove redundant instructions
3. Consolidate similar sections
4. Use concise language without losing clarity
5. Preserve the skill's core behavior exactly

## Performance Data
- Avg tokens per run: ${Math.round(metrics.avgTokensIn + metrics.avgTokensOut)}
- Avg execution time: ${Math.round(metrics.avgExecutionMs)}ms
- P95 latency: ${Math.round(metrics.p95ExecutionMs)}ms
- Failure rate: ${(metrics.failureRate * 100).toFixed(1)}%
- Total runs analyzed: ${metrics.totalRuns}
- Optimization score: ${score}/100

## Issues Found
${reasons.map(r => `- ${r}`).join('\n')}

## Current Skill Content
\`\`\`markdown
${skillContent}
\`\`\`

## Output Format
Return ONLY the optimized skill content in markdown. No explanations.
Include a comment at the top: \`<!-- Optimized by Skill Forge v0.1 | Estimated savings: X% tokens -->\``;
}

export function buildValidationPrompt(
  original: string,
  optimized: string,
  testInput: string
): string {
  return `Compare these two skill versions and determine if they produce equivalent outputs.

## Original
\`\`\`markdown
${original}
\`\`\`

## Optimized
\`\`\`markdown
${optimized}
\`\`\`

## Test Input
${testInput}

## Respond with JSON:
{
  "equivalent": true/false,
  "confidence": 0.0-1.0,
  "differences": ["list of behavioral differences if any"]
}`;
}
