// Claude PreToolUse early warning for the generated root openapi.yml.
// Git/CI drift checks remain authoritative: arbitrary shell writes are not covered.
import { readFileSync } from 'node:fs';

const protectedName = 'openapi.yml';
const pathKeys = new Set(['file_path', 'notebook_path', 'path', 'old_path', 'new_path', 'source_path', 'destination_path']);
const patchKeys = new Set(['patch', 'diff', 'patch_text']);

function fail(reason) {
  process.stderr.write(`[protected-edits] ${reason}\n`);
  process.exitCode = 2;
}

function isProtected(value) {
  if (typeof value !== 'string') return false;
  const normalized = value.replaceAll('\\', '/').replace(/^['"]|['"]$/g, '').trim();
  return normalized.split('/').at(-1) === protectedName;
}

function patchPaths(patch) {
  const paths = [];
  let sawPatch = false;
  for (const line of patch.split(/\r?\n/)) {
    if (line === '*** Begin Patch' || line.startsWith('diff --git ')) sawPatch = true;
    const match = line.match(/^(?:\*\*\* (?:Add File|Delete File|Update File|Move to): |\+\+\+ |--- )(.+)$/);
    if (match && match[1] !== '/dev/null') {
      const path = match[1].replace(/^[ab]\//, '').trim();
      if (path) paths.push(path);
    }
  }
  if (sawPatch && paths.length === 0) throw new Error('patch has no recognized file path');
  return paths;
}

function collectPaths(value, paths) {
  if (Array.isArray(value)) {
    for (const item of value) collectPaths(item, paths);
  } else if (value && typeof value === 'object') {
    for (const [key, child] of Object.entries(value)) {
      if (pathKeys.has(key) && typeof child === 'string') paths.push(child);
      if ((key === 'file_paths' || key === 'paths') && Array.isArray(child)) {
        paths.push(...child.filter(item => typeof item === 'string'));
      }
      if (patchKeys.has(key) && typeof child === 'string') paths.push(...patchPaths(child));
      if (typeof child === 'object') collectPaths(child, paths);
    }
  }
}

try {
  const payload = JSON.parse(readFileSync(0, 'utf8'));
  if (!payload || typeof payload !== 'object' || Array.isArray(payload)) throw new Error('invalid payload object');
  const name = payload.tool_name;
  const input = payload.tool_input;
  if (typeof name !== 'string' || !input || typeof input !== 'object') throw new Error('missing tool name/input');
  const editTools = new Set(['Write', 'Edit', 'MultiEdit', 'NotebookEdit']);
  let paths = [];
  if (editTools.has(name)) {
    collectPaths(input, paths);
    if (paths.length === 0) throw new Error('edit payload has no recognized file path');
  } else if (name === 'Bash') {
    const command = input.command;
    if (typeof command !== 'string') throw new Error('Bash payload has no command');
    if (!/\bapply_patch\b/.test(command)) process.exit(0);
    paths = patchPaths(command);
    if (paths.length === 0) throw new Error('apply_patch command has no recognized file path');
  } else {
    process.exit(0);
  }
  if (paths.some(isProtected)) fail('BLOCKED direct edit of generated openapi.yml; edit spec/**/*.tsp and rebuild.');
} catch (error) {
  fail(`Cannot verify Claude edit payload: ${error.message}`);
}
