import { ForgeDB } from './db';
import { Profiler } from './core';
import fs from 'fs';
import path from 'path';

async function main() {
  const args = process.argv.slice(2);
  const skillFlag = args.find(a => a.startsWith('--skill='));
  const iterFlag = args.find(a => a.startsWith('--iterations='));
  const dirFlag = args.find(a => a.startsWith('--dir='));
  const iterations = iterFlag ? parseInt(iterFlag.split('=')[1]) : 5;

  const db = new ForgeDB();
  const profiler = new Profiler(db);

  if (skillFlag) {
    // Profile a specific skill
    const skillPath = skillFlag.split('=')[1];
    const resolved = path.resolve(skillPath, 'SKILL.md');
    if (!fs.existsSync(resolved)) {
      console.error(`SKILL.md not found at ${resolved}`);
      process.exit(1);
    }
    console.log(`⚡ Profiling ${path.basename(skillPath)} (${iterations} iterations)...`);
    const metrics = await profiler.profileSkillFile(resolved, iterations);
    console.log(`✅ Done:`, metrics);
  } else if (dirFlag) {
    // Profile all skills in a directory
    const dir = path.resolve(dirFlag.split('=')[1]);
    const skills = fs.readdirSync(dir).filter(d =>
      fs.existsSync(path.join(dir, d, 'SKILL.md'))
    );
    console.log(`⚡ Found ${skills.length} skills in ${dir}`);
    for (const skill of skills) {
      console.log(`  Profiling ${skill}...`);
      await profiler.profileSkillFile(path.join(dir, skill, 'SKILL.md'), iterations);
    }
    console.log(`✅ Profiled ${skills.length} skills`);
  } else {
    console.log('Usage:');
    console.log('  forge profile --skill=<path-to-skill> [--iterations=5]');
    console.log('  forge profile --dir=<skills-directory> [--iterations=5]');
  }

  // Export dashboard data
  const data = db.exportDashboardData();
  const outDir = path.join(process.cwd(), 'demo', 'data');
  fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(path.join(outDir, 'dashboard.json'), JSON.stringify(data, null, 2));
  console.log(`📊 Dashboard data written to demo/data/dashboard.json`);

  db.close();
}

main().catch(console.error);
