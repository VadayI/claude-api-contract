#!/usr/bin/env node
/**
 * scripts/check_endpoints_registry.mjs
 *
 * Contract-completeness gate: every (method, path) operation defined in the
 * canonical openapi.yml must have a matching entry in the verification registry
 * .claude/memory/endpoints.json (see .claude/rules/verification.md —
 * "the contract is incomplete until the registry entry exists").
 *
 * This is a STATE check (not diff-scoped): it compares two committed artifacts,
 * so it never false-positives on model/description-only contract changes — it
 * fails only when an endpoint exists in the contract but is missing from the
 * registry (or vice-versa, reported as an informational note).
 *
 * Exit 0 = OK / cleanly skipped (no contract yet). Exit 1 = coverage gap.
 *
 * Run: npm run check:endpoints   (or: node scripts/check_endpoints_registry.mjs)
 */

import { readFileSync, existsSync } from 'node:fs';
import { parse } from 'yaml';

const OPENAPI = 'openapi.yml';
const REGISTRY = '.claude/memory/endpoints.json';
const HTTP_METHODS = new Set(['get', 'put', 'post', 'delete', 'options', 'head', 'patch', 'trace']);
const key = (m, p) => `${String(m).toUpperCase()} ${p}`;

// 1) No contract yet (fresh template scaffold) → nothing to verify.
if (!existsSync(OPENAPI)) {
  console.log(`[endpoints-registry] ${OPENAPI} absent — skip (no contract yet).`);
  process.exit(0);
}

let doc;
try {
  doc = parse(readFileSync(OPENAPI, 'utf8'));
} catch (e) {
  console.error(`::error::failed to parse ${OPENAPI}: ${e.message}`);
  process.exit(1);
}

const paths = (doc && typeof doc === 'object' && doc.paths) || {};
const contractOps = [];
for (const [p, item] of Object.entries(paths)) {
  if (!item || typeof item !== 'object') continue;
  for (const method of Object.keys(item)) {
    if (HTTP_METHODS.has(method.toLowerCase())) contractOps.push({ method: method.toUpperCase(), path: p });
  }
}

if (contractOps.length === 0) {
  console.log('[endpoints-registry] openapi.yml defines no operations — nothing to check.');
  process.exit(0);
}

// 2) Contract has operations → the registry is required.
if (!existsSync(REGISTRY)) {
  console.error(`::error::${REGISTRY} is missing but openapi.yml defines ${contractOps.length} operation(s). The verification registry is required (verification.md).`);
  process.exit(1);
}

let registry;
try {
  registry = JSON.parse(readFileSync(REGISTRY, 'utf8'));
} catch (e) {
  console.error(`::error::${REGISTRY} is not valid JSON: ${e.message}`);
  process.exit(1);
}
if (!Array.isArray(registry)) {
  console.error(`::error::${REGISTRY} must be a JSON array of endpoint objects.`);
  process.exit(1);
}

const registered = new Set(registry.map((e) => key(e.method, e.path)));
const contractKeys = new Set(contractOps.map((op) => key(op.method, op.path)));

// 3) Every contract operation must be registered (the hard gate).
const missing = contractOps.filter((op) => !registered.has(key(op.method, op.path)));
// 4) Registry entries with no matching contract operation — informational (stale?).
const stale = registry.map((e) => key(e.method, e.path)).filter((k) => !contractKeys.has(k));

if (missing.length > 0) {
  console.error(`::error::${missing.length} operation(s) in openapi.yml are not recorded in ${REGISTRY}:`);
  for (const op of missing) console.error(`  - ${key(op.method, op.path)}`);
  console.error('Add one entry per endpoint (method, path, tag, operationId, auth, scopes, statuses, envelope) — verification.md.');
  process.exit(1);
}

if (stale.length > 0) {
  console.log(`[endpoints-registry] note: ${stale.length} registry entr(y/ies) have no matching openapi operation (stale?):`);
  for (const k of stale) console.log(`  - ${k}`);
}

console.log(`[endpoints-registry] OK — all ${contractOps.length} operation(s) recorded in the registry.`);
