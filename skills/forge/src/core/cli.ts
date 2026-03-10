import { ForgeOrchestrator } from './orchestrator';
import path from 'path';

async function main() {
  const args = process.argv.slice(2);
  const dirFlag = args.find(a => a.startsWith('--dir=') || !a.startsWith('--'));
  const dryRun = args.includes('--dry-run');
  const iterFlag = args.find(a => a.startsWith('--iterations='));
  const iterations = iterFlag ? parseInt(iterFlag.split('=')[1]) : 5;

  const skillsDir = dirFlag
    ? path.resolve(dirFlag.startsWith('--dir=') ? dirFlag.split('=')[1] : dirFlag)
    : path.resolve('skills');

  const forge = new ForgeOrchestrator();
  await forge.forge(skillsDir, { iterations, dryRun });
}

main().catch(console.error);
