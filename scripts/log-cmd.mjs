/**
 * scripts/log-cmd.mjs
 *
 * Appends one JSONL entry to .claude/memory/command-log.jsonl.
 *
 * Usage: node scripts/log-cmd.mjs <cmd> [args]
 *   e.g. node scripts/log-cmd.mjs /validate-contract ""
 *
 * Creates .claude/memory/ and the log file if they do not exist.
 * Never throws — failures are silent so they never disrupt the session.
 */

import { mkdirSync, appendFileSync } from 'node:fs';
import { argv } from 'node:process';

try {
  const cmd  = argv[2] ?? '(unknown)';
  const args = argv[3] ?? '';

  const entry = JSON.stringify({
    ts:   new Date().toISOString(),
    cmd,
    args,
  });

  const dir  = '.claude/memory';
  const file = `${dir}/command-log.jsonl`;

  mkdirSync(dir, { recursive: true });
  appendFileSync(file, entry + '\n', 'utf8');
} catch {
  // intentionally silent — log failures must never abort the session
}
