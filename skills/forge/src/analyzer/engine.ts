import { ForgeDB } from '../profiler/db';
import { AggregatedMetrics, AnalysisResult } from '../types';

export class Analyzer {
  private db: ForgeDB;

  constructor(db: ForgeDB) {
    this.db = db;
  }

  /**
   * Analyze all tracked skills and rank by optimization potential.
   * Score 0-100: higher means more wasteful / better optimization candidate.
   */
  analyzeAll(): AnalysisResult[] {
    const skillIds = this.db.getAllSkillIds();
    return skillIds
      .map(id => this.analyze(id))
      .sort((a, b) => b.score - a.score);
  }

  analyze(skillId: string): AnalysisResult {
    const metrics = this.db.getAggregate(skillId);
    const reasons: string[] = [];
    let score = 0;

    // Factor 1: Token usage (weight: 30)
    const totalTokens = metrics.avgTokensIn + metrics.avgTokensOut;
    if (totalTokens > 2000) {
      score += Math.min(30, (totalTokens - 2000) / 100);
      reasons.push(`High token usage: ${Math.round(totalTokens)} avg tokens/run`);
    }

    // Factor 2: Execution time (weight: 25)
    if (metrics.avgExecutionMs > 2000) {
      score += Math.min(25, (metrics.avgExecutionMs - 2000) / 200);
      reasons.push(`Slow execution: ${Math.round(metrics.avgExecutionMs)}ms avg`);
    }

    // Factor 3: P95 latency spikes (weight: 20)
    if (metrics.p95ExecutionMs > metrics.avgExecutionMs * 2) {
      score += 20;
      reasons.push(`Latency spikes: P95 ${Math.round(metrics.p95ExecutionMs)}ms vs avg ${Math.round(metrics.avgExecutionMs)}ms`);
    }

    // Factor 4: Failure rate (weight: 15)
    if (metrics.failureRate > 0.05) {
      score += Math.min(15, metrics.failureRate * 100);
      reasons.push(`High failure rate: ${(metrics.failureRate * 100).toFixed(1)}%`);
    }

    // Factor 5: Volume (weight: 10) — high-volume skills benefit most from optimization
    if (metrics.totalRuns > 20) {
      score += Math.min(10, metrics.totalRuns / 10);
      reasons.push(`High volume: ${metrics.totalRuns} runs`);
    }

    score = Math.min(100, Math.round(score));

    let recommendation: AnalysisResult['recommendation'] = 'ok';
    if (score >= 50) recommendation = 'optimize';
    else if (score >= 25) recommendation = 'monitor';

    return { skillId, metrics, score, reasons, recommendation };
  }
}
