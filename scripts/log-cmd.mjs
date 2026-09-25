/**
 * scripts/log-cmd.mjs
 *
 * Appends one JSONL entry to .ai-runtime/command-log.jsonl (a legacy
 * .claude/memory/command-log.jsonl is moved there first; see runtime-state.mjs).
 *
 * Usage: node scripts/log-cmd.mjs <cmd> [args]
 *   e.g. node scripts/log-cmd.mjs /validate-contract ""
 *
 * Creates .ai-runtime/ and the log file if they do not exist.
 * Never throws — failures are silent so they never disrupt the session; a
 * conflict between two different log copies is the one case that is reported.
 */

import { appendFileSync } from 'node:fs';
import { argv } from 'node:process';
import { runtimeStatePath } from './runtime-state.mjs';

try {
  const cmd  = argv[2] ?? '(unknown)';
  const args = argv[3] ?? '';

  const entry = JSON.stringify({
    ts:   new Date().toISOString(),
    cmd,
    args,
  });

  appendFileSync(runtimeStatePath('command-log.jsonl'), entry + '\n', 'utf8');
} catch (err) {
  // Celowo cicho — poza konfliktem kopii, który człowiek musi rozstrzygnąć.
  if (err && /Conflicting runtime state copies/.test(err.message)) {
    console.error(`[log-cmd] ${err.message}`);
  }
}
