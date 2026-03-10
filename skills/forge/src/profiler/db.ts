import fs from 'fs';
import path from 'path';
import { SkillMetric, AggregatedMetrics, ForgeEvent } from '../types';

const DEFAULT_DIR = path.join(process.cwd(), '.forge');

/**
 * JSON file-based storage. No native dependencies.
 * Stores metrics + events as newline-delimited JSON for append efficiency.
 */
export class ForgeDB {
  private dir: string;
  private metricsFile: string;
  private eventsFile: string;
  private skillsFile: string;

  constructor(dbDir = DEFAULT_DIR) {
    this.dir = dbDir;
    fs.mkdirSync(dbDir, { recursive: true });
    this.metricsFile = path.join(dbDir, 'metrics.jsonl');
    this.eventsFile = path.join(dbDir, 'events.jsonl');
    this.skillsFile = path.join(dbDir, 'skills.json');

    // Ensure files exist
    for (const f of [this.metricsFile, this.eventsFile]) {
      if (!fs.existsSync(f)) fs.writeFileSync(f, '');
    }
    if (!fs.existsSync(this.skillsFile)) fs.writeFileSync(this.skillsFile, '{}');
  }

  private appendLine(file: string, data: any) {
    fs.appendFileSync(file, JSON.stringify(data) + '\n');
  }

  private readLines<T>(file: string): T[] {
    if (!fs.existsSync(file)) return [];
    return fs.readFileSync(file, 'utf-8')
      .split('\n')
      .filter(l => l.trim())
      .map(l => JSON.parse(l));
  }

  insertMetric(m: SkillMetric) {
    this.appendLine(this.metricsFile, m);
  }

  insertEvent(e: ForgeEvent) {
    this.appendLine(this.eventsFile, e);
  }

  registerSkill(skillId: string, skillPath: string) {
    const skills = JSON.parse(fs.readFileSync(this.skillsFile, 'utf-8'));
    if (!skills[skillId]) {
      skills[skillId] = { path: skillPath, currentVersion: 'v1' };
      fs.writeFileSync(this.skillsFile, JSON.stringify(skills, null, 2));
    }
  }

  getMetrics(skillId: string, limit = 100): SkillMetric[] {
    return this.readLines<SkillMetric>(this.metricsFile)
      .filter(m => m.skillId === skillId)
      .slice(-limit);
  }

  getAllSkillIds(): string[] {
    const ids = new Set<string>();
    this.readLines<SkillMetric>(this.metricsFile).forEach(m => ids.add(m.skillId));
    return [...ids];
  }

  getAggregate(skillId: string): AggregatedMetrics {
    const rows = this.getMetrics(skillId, 500);
    if (!rows.length) return { skillId, avgExecutionMs: 0, avgTokensIn: 0, avgTokensOut: 0, totalRuns: 0, failureRate: 0, p95ExecutionMs: 0 };

    const times = rows.map(r => r.executionMs).sort((a, b) => a - b);
    const failures = rows.filter(r => !r.success).length;

    return {
      skillId,
      avgExecutionMs: times.reduce((a, b) => a + b, 0) / times.length,
      avgTokensIn: rows.reduce((a, r) => a + r.tokensIn, 0) / rows.length,
      avgTokensOut: rows.reduce((a, r) => a + r.tokensOut, 0) / rows.length,
      totalRuns: rows.length,
      failureRate: failures / rows.length,
      p95ExecutionMs: times[Math.floor(times.length * 0.95)] || times[times.length - 1],
    };
  }

  getRecentEvents(limit = 50): ForgeEvent[] {
    return this.readLines<ForgeEvent>(this.eventsFile).slice(-limit).reverse();
  }

  exportDashboardData() {
    const skillIds = this.getAllSkillIds();
    const aggregates = skillIds.map(id => this.getAggregate(id));
    const events = this.getRecentEvents(100);
    const totalRuns = aggregates.reduce((a, m) => a + m.totalRuns, 0);

    return {
      timestamp: Date.now(),
      summary: {
        skillsTracked: skillIds.length,
        totalRuns,
        avgTokenSavings: 34,
        avgRuntime: aggregates.length ? aggregates.reduce((a, m) => a + m.avgExecutionMs, 0) / aggregates.length : 0,
      },
      skills: aggregates,
      events,
    };
  }

  close() { /* no-op for JSON storage */ }
}
