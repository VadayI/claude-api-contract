#!/usr/bin/env node
/**
 * scripts/check_endpoints_registry.mjs
 *
 * Contract-completeness + endpoint-surface gate
 * (.claude/rules/verification.md + .claude/rules/endpoint-surface.md).
 *
 * Compares three committed artifacts — openapi.yml, .claude/memory/endpoints.json,
 * and the OPTIONAL .claude/memory/pages.json page-map — and fails (exit 1) on:
 *   1. coverage   — an operation in openapi.yml with no registry entry;
 *   2. x-surface  — an operation missing/!valid x-surface (must be resource|system);
 *   3. drift      — a registry entry whose surface != the operation's x-surface;
 *   4. page-map   — a page entry that is malformed, sits under /api/v1/, or
 *                   consumes a missing or `system` operation.
 *
 * STATE check (not diff-scoped): never false-positives on model/description-only
 * edits. Exit 0 = OK / cleanly skipped (no contract yet). Exit 1 = a gap.
 *
 * Run: npm run check:endpoints   (or: node scripts/check_endpoints_registry.mjs)
 */

import { readFileSync, existsSync } from 'node:fs';
import { parse } from 'yaml';

const OPENAPI = 'openapi.yml';
const REGISTRY = '.claude/memory/endpoints.json';
const PAGES = '.claude/memory/pages.json';
const HTTP_METHODS = new Set(['get', 'put', 'post', 'delete', 'options', 'head', 'patch', 'trace']);
const SURFACES = new Set(['resource', 'system']);
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
    if (!HTTP_METHODS.has(method.toLowerCase())) continue;
    const op = item[method] || {};
    contractOps.push({ method: method.toUpperCase(), path: p, operationId: op.operationId, xSurface: op['x-surface'] });
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

const regByKey = new Map(registry.map((e) => [key(e.method, e.path), e]));
const registered = new Set(regByKey.keys());
const contractKeys = new Set(contractOps.map((op) => key(op.method, op.path)));
const opIds = new Set(contractOps.map((op) => op.operationId).filter(Boolean));
const systemOpIds = new Set(contractOps.filter((op) => op.xSurface === 'system').map((op) => op.operationId));

const errors = [];

// (1) coverage — every contract operation must be registered.
for (const op of contractOps)
  if (!registered.has(key(op.method, op.path)))
    errors.push(`coverage: ${key(op.method, op.path)} is in openapi.yml but not in ${REGISTRY} (add an entry — verification.md)`);

// (2)+(3) x-surface presence/validity and registry ↔ contract consistency.
for (const op of contractOps) {
  const k = key(op.method, op.path);
  if (!SURFACES.has(op.xSurface))
    errors.push(`x-surface: ${k} has x-surface=${JSON.stringify(op.xSurface)} in openapi.yml — must be one of ${[...SURFACES].join('|')} (endpoint-surface.md)`);
  const entry = regByKey.get(k);
  if (entry) {
    if (!SURFACES.has(entry.surface))
      errors.push(`registry: ${k} has surface=${JSON.stringify(entry.surface)} in ${REGISTRY} — must be one of ${[...SURFACES].join('|')}`);
    else if (SURFACES.has(op.xSurface) && entry.surface !== op.xSurface)
      errors.push(`drift: ${k} surface mismatch — openapi x-surface=${op.xSurface} vs registry surface=${entry.surface}`);
  }
}

// (4) page-map integrity — OPTIONAL file (absent on a fresh scaffold).
if (existsSync(PAGES)) {
  let pages;
  try {
    pages = JSON.parse(readFileSync(PAGES, 'utf8'));
  } catch (e) {
    console.error(`::error::${PAGES} is not valid JSON: ${e.message}`);
    process.exit(1);
  }
  if (!Array.isArray(pages)) {
    console.error(`::error::${PAGES} must be a JSON array of page objects.`);
    process.exit(1);
  }
  for (const pg of pages) {
    const r = pg && pg.route;
    if (typeof r !== 'string' || !r.startsWith('/')) {
      errors.push(`page-map: an entry has an invalid route ${JSON.stringify(r)}`);
      continue;
    }
    if (pg.surface !== 'page')
      errors.push(`page-map: ${r} must have surface="page" (got ${JSON.stringify(pg.surface)})`);
    if (r.startsWith('/api/v1/'))
      errors.push(`page-map: ${r} is a frontend route and must NOT sit under /api/v1/ (that namespace is API operations — endpoint-surface.md)`);
    const consumes = Array.isArray(pg.consumes) ? pg.consumes : [];
    for (const id of consumes) {
      if (!opIds.has(id))
        errors.push(`page-map: ${r} consumes "${id}" which is not an operationId in openapi.yml`);
      else if (systemOpIds.has(id))
        errors.push(`page-map: ${r} consumes "${id}" — a page must never target a system operation (endpoint-surface.md)`);
    }
  }
}

// Registry entries with no matching contract operation — informational (stale?).
const stale = registry.map((e) => key(e.method, e.path)).filter((k) => !contractKeys.has(k));

if (errors.length > 0) {
  console.error(`::error::${errors.length} endpoint-surface / registry problem(s):`);
  for (const m of errors) console.error(`  - ${m}`);
  console.error('See .claude/rules/endpoint-surface.md and .claude/rules/verification.md.');
  process.exit(1);
}

if (stale.length > 0) {
  console.log(`[endpoints-registry] note: ${stale.length} registry entr(y/ies) have no matching openapi operation (stale?):`);
  for (const k of stale) console.log(`  - ${k}`);
}

const pageNote = existsSync(PAGES) ? '; page-map valid' : '';
console.log(`[endpoints-registry] OK — ${contractOps.length} operation(s) registered; x-surface present & consistent${pageNote}.`);
