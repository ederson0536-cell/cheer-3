import fs from 'fs';
import path from 'path';
import { ForgeDB } from '../profiler/db';
import { Analyzer } from '../analyzer/engine';
import { buildOptimizationPrompt } from './prompts';
import { AnalysisResult, OptimizationResult } from '../types';

export class Optimizer {
  private db: ForgeDB;
  private analyzer: Analyzer;

  constructor(db: ForgeDB) {
    this.db = db;
    this.analyzer = new Analyzer(db);
  }

  /**
   * Optimize a skill by generating an improved version.
   * In production, this calls an LLM. For now, applies heuristic rules.
   */
  async optimize(skillId: string, skillPath: string): Promise<OptimizationResult> {
    const analysis = this.analyzer.analyze(skillId);
    const content = fs.readFileSync(skillPath, 'utf-8');
    const prompt = buildOptimizationPrompt(content, analysis);

    // Heuristic optimization (replace with LLM call in production)
    const optimized = this.heuristicOptimize(content, analysis);

    // Write optimized version
    const dir = path.dirname(skillPath);
    const optimizedPath = path.join(dir, 'SKILL.optimized.md');
    fs.writeFileSync(optimizedPath, optimized);

    const originalTokens = Math.floor(content.length / 4);
    const optimizedTokens = Math.floor(optimized.length / 4);

    const result: OptimizationResult = {
      skillId,
      originalPath: skillPath,
      optimizedPath,
      optimizedContent: optimized,
      changes: this.diffChanges(content, optimized),
      estimatedSavings: {
        tokens: originalTokens - optimizedTokens,
        timeMs: Math.round(analysis.metrics.avgExecutionMs * 0.15),
      },
    };

    this.db.insertEvent({
      timestamp: Date.now(),
      module: 'optimizer',
      action: 'optimized',
      skillId,
      details: `Saved ~${result.estimatedSavings.tokens} tokens (${Math.round((result.estimatedSavings.tokens / originalTokens) * 100)}%)`,
    });

    return result;
  }

  private heuristicOptimize(content: string, analysis: AnalysisResult): string {
    let optimized = content;

    // Remove excessive blank lines
    optimized = optimized.replace(/\n{3,}/g, '\n\n');

    // Remove HTML comments
    optimized = optimized.replace(/<!--[\s\S]*?-->/g, '');

    // Condense verbose bullet points
    optimized = optimized.replace(/^(\s*[-*]\s+)(.{200,})/gm, (_, prefix, text) => {
      // Truncate overly long bullets
      const shortened = text.substring(0, 150).replace(/\s+\S*$/, '…');
      return prefix + shortened;
    });

    // Remove duplicate instructions (lines that appear >1 time)
    const lines = optimized.split('\n');
    const seen = new Set<string>();
    const deduped = lines.filter(line => {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith('#')) return true;
      if (seen.has(trimmed)) return false;
      seen.add(trimmed);
      return true;
    });
    optimized = deduped.join('\n');

    // Add optimization header
    const savings = Math.round((1 - optimized.length / content.length) * 100);
    optimized = `<!-- Optimized by Skill Forge v0.1 | Estimated savings: ${savings}% tokens -->\n${optimized}`;

    return optimized;
  }

  private diffChanges(original: string, optimized: string): string[] {
    const changes: string[] = [];
    const origLines = original.split('\n').length;
    const optLines = optimized.split('\n').length;
    const origChars = original.length;
    const optChars = optimized.length;

    if (optLines < origLines) changes.push(`Reduced from ${origLines} to ${optLines} lines`);
    if (optChars < origChars) changes.push(`${Math.round((1 - optChars / origChars) * 100)}% fewer characters`);

    return changes;
  }
}
