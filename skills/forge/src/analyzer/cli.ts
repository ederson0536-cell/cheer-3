import { ForgeDB } from '../profiler/db';
import { Analyzer } from './engine';
import fs from 'fs';
import path from 'path';

async function main() {
  const db = new ForgeDB();
  const analyzer = new Analyzer(db);

  console.log('🔍 Analyzing all tracked skills...\n');

  const results = analyzer.analyzeAll();

  if (!results.length) {
    console.log('No skills profiled yet. Run `forge profile` first.');
    db.close();
    return;
  }

  // Display results
  for (const r of results) {
    const icon = r.recommendation === 'optimize' ? '🔴' : r.recommendation === 'monitor' ? '🟡' : '🟢';
    console.log(`${icon} ${r.skillId} — score: ${r.score}/100 → ${r.recommendation}`);
    for (const reason of r.reasons) {
      console.log(`   └─ ${reason}`);
    }
    console.log();
  }

  // Log events
  for (const r of results) {
    db.insertEvent({
      timestamp: Date.now(),
      module: 'analyzer',
      action: r.recommendation,
      skillId: r.skillId,
      details: `Score ${r.score}: ${r.reasons.join('; ')}`,
    });
  }

  // Export analysis data
  const outDir = path.join(process.cwd(), 'demo', 'data');
  fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(path.join(outDir, 'analysis.json'), JSON.stringify(results, null, 2));
  fs.writeFileSync(path.join(outDir, 'dashboard.json'), JSON.stringify(db.exportDashboardData(), null, 2));
  console.log('📊 Analysis + dashboard data exported to demo/data/');

  db.close();
}

main().catch(console.error);
