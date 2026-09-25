/**
 * scripts/runtime-state.mjs
 *
 * Kanoniczne ścieżki maszynowych rekordów runtime dla writerów Node
 * (detect-env.mjs, log-cmd.mjs). Odzwierciedla regułę
 * `scripts/ai/project_state.py --migrate-runtime` dla JEDNEGO artefaktu:
 *   - tylko canonical istnieje         -> użyj canonical;
 *   - tylko legacy (.claude/memory)     -> przenieś do .ai-runtime, potem użyj;
 *   - oba identyczne                    -> usuń legacy, użyj canonical;
 *   - oba różne                         -> błąd: writer odmawia, człowiek robi diff.
 * Rejestry projektu (endpoints/routes/pages) NIE są tu migrowane — to robi
 * wyłącznie jawne `python scripts/ai/project_state.py --root . --apply`.
 */

import { existsSync, mkdirSync, readFileSync, renameSync, unlinkSync, lstatSync } from 'node:fs';
import { dirname, join } from 'node:path';

const LEGACY_DIRECTORY = '.claude/memory';
const RUNTIME_DIRECTORY = '.ai-runtime';
const RUNTIME_ARTIFACTS = new Set(['env-detect.json', 'command-log.jsonl']);

function rejectLink(path) {
  // Dowiązania w ścieżkach stanu nie są obsługiwane — tak samo jak w project_state.py.
  if (existsSync(path) && lstatSync(path).isSymbolicLink()) {
    throw new Error(`Linked runtime state path: ${path}`);
  }
}

/**
 * Zwraca kanoniczną ścieżkę zapisu dla allowlistowanego artefaktu runtime,
 * migrując wcześniej jego kopię legacy bez utraty danych.
 *
 * @param {string} name  basename artefaktu: env-detect.json | command-log.jsonl
 * @param {string} root  katalog repozytorium (domyślnie cwd)
 * @returns {string} ścieżka `<root>/.ai-runtime/<name>`
 * @throws {Error} dla nieznanej nazwy, dowiązań albo konfliktu dwóch różnych kopii
 */
export function runtimeStatePath(name, root = process.cwd()) {
  if (!RUNTIME_ARTIFACTS.has(name)) {
    throw new Error(`Unknown runtime state artifact: ${name}`);
  }
  const canonical = join(root, RUNTIME_DIRECTORY, name);
  const legacy = join(root, LEGACY_DIRECTORY, name);
  for (const path of [join(root, RUNTIME_DIRECTORY), canonical, join(root, LEGACY_DIRECTORY), legacy]) {
    rejectLink(path);
  }
  if (existsSync(legacy)) {
    if (!existsSync(canonical)) {
      mkdirSync(dirname(canonical), { recursive: true });
      renameSync(legacy, canonical);
    } else if (readFileSync(legacy).equals(readFileSync(canonical))) {
      unlinkSync(legacy);
    } else {
      throw new Error(
        `Conflicting runtime state copies: ${legacy} and ${canonical}. ` +
          'Compare them and remove one; run: python scripts/ai/project_state.py --root .',
      );
    }
  }
  mkdirSync(dirname(canonical), { recursive: true });
  return canonical;
}
