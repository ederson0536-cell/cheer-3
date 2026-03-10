import { ForgeDB } from '../profiler/db';
import { Validator } from './abtest';
import path from 'path';
import fs from 'fs';

async function main() {
  const args = process.argv.slice(2);
  const skillFlag = args.find(a => a.startsWith('--skill='));

  if (!skillFlag) {
    console.log('Usage: forge validate --skill=<path-to-skill>');
    process.exit(1);
  }

  const db = new ForgeDB();
  const validator = new Validator(db);

  const skillPath = skillFlag.split('=')[1];
  const skillId = path.basename(skillPath);
  const originalPath = path.resolve(skillPath, 'SKILL.md');
  const optimizedPath = path.resolve(skillPath, 'SKILL.optimized.md');

  if (!fs.existsSync(optimizedPath)) {
    console.error(`No optimized version found. Run \`forge optimize --skill=${skillPath}\` first.`);
    process.exit(1);
  }

  console.log(`✅ Validating ${skillId}: original vs optimized...`);
  const result = await validator.validate(skillId, originalPath, optimizedPath);

  console.log(`\nResult: ${result.passed ? '✅ PASSED' : '❌ FAILED'}`);
  console.log(`  Similarity: ${(result.similarityScore * 100).toFixed(0)}%`);
  console.log(`  Speed improvement: ${(result.speedImprovement * 100).toFixed(0)}%`);
  console.log(`  Token savings: ${(result.tokenSavings * 100).toFixed(0)}%`);

  if (result.passed) {
    db.insertEvent({
      timestamp: Date.now(),
      module: 'forge',
      action: 'promoted',
      skillId,
      details: 'v2 promoted after passing validation',
    });
    console.log(`\n🚀 ${skillId} v2 promoted!`);
  }

  // Export
  const outDir = path.join(process.cwd(), 'demo', 'data');
  fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(path.join(outDir, 'dashboard.json'), JSON.stringify(db.exportDashboardData(), null, 2));

  db.close();
}

main().catch(console.error);
