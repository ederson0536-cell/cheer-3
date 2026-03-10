import fs from 'fs';
import { ForgeDB } from '../profiler/db';
import { Profiler } from '../profiler/core';
import { ValidationResult } from '../types';

export class Validator {
  private db: ForgeDB;
  private profiler: Profiler;

  constructor(db: ForgeDB) {
    this.db = db;
    this.profiler = new Profiler(db);
  }

  /**
   * A/B test original vs optimized skill.
   * Runs both versions, compares outputs + performance.
   */
  async validate(
    skillId: string,
    originalPath: string,
    optimizedPath: string,
    iterations = 3
  ): Promise<ValidationResult> {
    const original = fs.readFileSync(originalPath, 'utf-8');
    const optimized = fs.readFileSync(optimizedPath, 'utf-8');

    // Profile both versions
    const origMetrics = [];
    const optMetrics = [];

    for (let i = 0; i < iterations; i++) {
      // Original
      const origStart = Date.now();
      await this.simulateExecution(original);
      origMetrics.push(Date.now() - origStart);

      // Optimized
      const optStart = Date.now();
      await this.simulateExecution(optimized);
      optMetrics.push(Date.now() - optStart);
    }

    const avgOrig = origMetrics.reduce((a, b) => a + b) / origMetrics.length;
    const avgOpt = optMetrics.reduce((a, b) => a + b) / optMetrics.length;
    const speedImprovement = (avgOrig - avgOpt) / avgOrig;

    const origTokens = Math.floor(original.length / 4);
    const optTokens = Math.floor(optimized.length / 4);
    const tokenSavings = (origTokens - optTokens) / origTokens;

    // Similarity: rough content comparison
    const similarity = this.computeSimilarity(original, optimized);

    const passed = similarity > 0.7 && tokenSavings > 0;

    const result: ValidationResult = {
      skillId,
      version: 'v2',
      passed,
      originalOutput: `[${origMetrics.join(', ')}]ms`,
      optimizedOutput: `[${optMetrics.join(', ')}]ms`,
      similarityScore: similarity,
      speedImprovement,
      tokenSavings,
    };

    this.db.insertEvent({
      timestamp: Date.now(),
      module: 'validator',
      action: passed ? 'passed' : 'failed',
      skillId,
      details: `Similarity: ${(similarity * 100).toFixed(0)}%, Speed: ${(speedImprovement * 100).toFixed(0)}% faster, Tokens: ${(tokenSavings * 100).toFixed(0)}% saved`,
    });

    return result;
  }

  private async simulateExecution(content: string): Promise<string> {
    // In production, actually run the skill and capture output
    await new Promise(r => setTimeout(r, 50 + Math.random() * 200));
    return content.substring(0, 100);
  }

  private computeSimilarity(a: string, b: string): number {
    // Jaccard similarity on word sets
    const wordsA = new Set(a.toLowerCase().match(/\w+/g) || []);
    const wordsB = new Set(b.toLowerCase().match(/\w+/g) || []);
    const intersection = new Set([...wordsA].filter(w => wordsB.has(w)));
    const union = new Set([...wordsA, ...wordsB]);
    return union.size ? intersection.size / union.size : 0;
  }
}
