import { ForgeDB } from '../profiler/db';
import { Optimizer } from './runner';
import { Analyzer } from '../analyzer/engine';
import fs from 'fs';
import path from 'path';

async function main() {
  const args = process.argv.slice(2);
  const skillFlag = args.find(a => a.startsWith('--skill='));

  const db = new ForgeDB();
  const optimizer = new Optimizer(db);

  if (skillFlag) {
    const skillPath = skillFlag.split('=')[1];
    const skillMd = path.resolve(skillPath, 'SKILL.md');
    const skillId = path.basename(skillPath);

    if (!fs.existsSync(skillMd)) {
      console.error(`SKILL.md not found at ${skillMd}`);
      process.exit(1);
    }

    console.log(`⚡ Optimizing ${skillId}...`);
    const result = await optimizer.optimize(skillId, skillMd);
    console.log(`✅ Optimized: ${result.changes.join(', ')}`);
    console.log(`   Saved ~${result.estimatedSavings.tokens} tokens`);
    console.log(`   Written to ${result.optimizedPath}`);
  } else {
    // Auto-optimize: pick top candidates from analyzer
    const analyzer = new Analyzer(db);
    const results = analyzer.analyzeAll().filter(r => r.recommendation === 'optimize');

    if (!results.length) {
      console.log('No skills need optimization. Run `forge analyze` to check.');
      db.close();
      return;
    }

    console.log(`⚡ Auto-optimizing ${results.length} skills...\n`);
    for (const r of results) {
      console.log(`  Optimizing ${r.skillId} (score: ${r.score})...`);
      // Would need skill path lookup from DB in production
    }
  }

  // Export updated dashboard data
  const outDir = path.join(process.cwd(), 'demo', 'data');
  fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(path.join(outDir, 'dashboard.json'), JSON.stringify(db.exportDashboardData(), null, 2));

  db.close();
}

main().catch(console.error);
