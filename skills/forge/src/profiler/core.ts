import fs from 'fs';
import path from 'path';
import { ForgeDB } from './db';
import { SkillMetric } from '../types';

export class Profiler {
  private db: ForgeDB;

  constructor(db: ForgeDB) {
    this.db = db;
  }

  /**
   * Wrap any async function and record its execution metrics.
   */
  async profile<T>(skillId: string, fn: () => Promise<T>, version = 'v1'): Promise<T> {
    const start = Date.now();
    let success = true;
    let result: T;

    try {
      result = await fn();
    } catch (err) {
      success = false;
      throw err;
    } finally {
      const executionMs = Date.now() - start;
      const metric: SkillMetric = {
        skillId,
        executionMs,
        tokensIn: this.estimateTokens(skillId),
        tokensOut: success ? this.estimateOutput(result!) : 0,
        success,
        timestamp: Date.now(),
        version,
      };
      this.db.insertMetric(metric);
      this.db.insertEvent({
        timestamp: Date.now(),
        module: 'profiler',
        action: 'recorded',
        skillId,
        details: `${executionMs}ms, ${metric.tokensIn}+${metric.tokensOut} tokens, ${success ? 'ok' : 'fail'}`,
      });
    }

    return result!;
  }

  /**
   * Profile a skill by reading its SKILL.md and simulating execution.
   * For real usage, this wraps the actual skill runner.
   */
  async profileSkillFile(skillPath: string, iterations = 5) {
    const skillId = path.basename(path.dirname(skillPath));
    const content = fs.readFileSync(skillPath, 'utf-8');

    this.db.registerSkill(skillId, skillPath);

    for (let i = 0; i < iterations; i++) {
      const tokensIn = Math.floor(content.length / 4);
      const start = Date.now();

      // Simulate skill execution with realistic variance
      await new Promise(r => setTimeout(r, 200 + Math.random() * 800));
      const executionMs = Date.now() - start;

      const metric: SkillMetric = {
        skillId,
        executionMs,
        tokensIn,
        tokensOut: Math.floor(tokensIn * (0.3 + Math.random() * 0.4)),
        success: Math.random() > 0.05,
        timestamp: Date.now(),
        version: 'v1',
      };
      this.db.insertMetric(metric);
    }

    this.db.insertEvent({
      timestamp: Date.now(),
      module: 'profiler',
      action: 'batch-complete',
      skillId,
      details: `Profiled ${iterations} iterations`,
    });

    return this.db.getAggregate(skillId);
  }

  private estimateTokens(skillId: string): number {
    // In production, hook into the LLM's token counter
    return 500 + Math.floor(Math.random() * 1500);
  }

  private estimateOutput(result: any): number {
    try {
      return Math.floor(JSON.stringify(result).length / 4);
    } catch {
      return 100;
    }
  }
}
