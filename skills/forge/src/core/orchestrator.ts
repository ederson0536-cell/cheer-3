import fs from 'fs';
import path from 'path';
import { ForgeDB } from '../profiler/db';
import { Profiler } from '../profiler/core';
import { Analyzer } from '../analyzer/engine';
import { Optimizer } from '../optimizer/runner';
import { Validator } from '../validator/abtest';

/**
 * Forge Core: Orchestrates the full pipeline.
 * Profile → Analyze → Optimize → Validate → Promote
 */
export class ForgeOrchestrator {
  private db: ForgeDB;
  private profiler: Profiler;
  private analyzer: Analyzer;
  private optimizer: Optimizer;
  private validator: Validator;

  constructor(dbPath?: string) {
    this.db = new ForgeDB(dbPath);
    this.profiler = new Profiler(this.db);
    this.analyzer = new Analyzer(this.db);
    this.optimizer = new Optimizer(this.db);
    this.validator = new Validator(this.db);
  }

  /**
   * Run the full forge pipeline on a skills directory.
   */
  async forge(skillsDir: string, options: { iterations?: number; dryRun?: boolean } = {}) {
    const { iterations = 5, dryRun = false } = options;

    console.log('🔥 SKILL FORGE v0.1\n');

    // Step 1: Profile
    console.log('━━━ STEP 1: PROFILE ━━━');
    const skills = fs.readdirSync(skillsDir).filter(d =>
      fs.existsSync(path.join(skillsDir, d, 'SKILL.md'))
    );
    console.log(`Found ${skills.length} skills\n`);

    for (const skill of skills) {
      const skillMd = path.join(skillsDir, skill, 'SKILL.md');
      console.log(`  📊 Profiling ${skill}...`);
      await this.profiler.profileSkillFile(skillMd, iterations);
    }

    // Step 2: Analyze
    console.log('\n━━━ STEP 2: ANALYZE ━━━');
    const analyses = this.analyzer.analyzeAll();
    for (const a of analyses) {
      const icon = a.recommendation === 'optimize' ? '🔴' : a.recommendation === 'monitor' ? '🟡' : '🟢';
      console.log(`  ${icon} ${a.skillId}: ${a.score}/100 → ${a.recommendation}`);
    }

    // Step 3: Optimize candidates
    const candidates = analyses.filter(a => a.recommendation === 'optimize');
    if (candidates.length === 0) {
      console.log('\n✅ All skills look healthy. Nothing to optimize.');
    } else {
      console.log(`\n━━━ STEP 3: OPTIMIZE (${candidates.length} skills) ━━━`);
      for (const c of candidates) {
        const skillMd = path.join(skillsDir, c.skillId, 'SKILL.md');
        if (!fs.existsSync(skillMd)) continue;

        if (dryRun) {
          console.log(`  ⏭  [dry-run] Would optimize ${c.skillId}`);
          continue;
        }

        console.log(`  ⚡ Optimizing ${c.skillId}...`);
        const result = await this.optimizer.optimize(c.skillId, skillMd);
        console.log(`     Saved ~${result.estimatedSavings.tokens} tokens`);

        // Step 4: Validate
        console.log(`  ✅ Validating ${c.skillId}...`);
        const validation = await this.validator.validate(
          c.skillId, skillMd, result.optimizedPath
        );

        if (validation.passed) {
          console.log(`  🚀 ${c.skillId} v2 PROMOTED (${(validation.tokenSavings * 100).toFixed(0)}% tokens saved)\n`);
        } else {
          console.log(`  ❌ ${c.skillId} v2 REJECTED (similarity too low)\n`);
        }
      }
    }

    // Export dashboard data
    this.exportData();

    console.log('\n🔥 Forge complete.');
    this.db.close();
  }

  exportData() {
    const data = this.db.exportDashboardData();
    const outDir = path.join(process.cwd(), 'demo', 'data');
    fs.mkdirSync(outDir, { recursive: true });
    fs.writeFileSync(path.join(outDir, 'dashboard.json'), JSON.stringify(data, null, 2));
    console.log('\n📊 Dashboard data → demo/data/dashboard.json');
  }
}
