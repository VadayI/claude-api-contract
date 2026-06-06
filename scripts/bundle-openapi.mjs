/**
 * scripts/bundle-openapi.mjs
 *
 * Copies the TypeSpec openapi3 emitter output to the canonical ./openapi.yml.
 *
 * `tsp compile spec --emit @typespec/openapi3` writes the schema under
 * tsp-output/@typespec/openapi3/openapi.yaml. The canonical, committed,
 * single-source-of-truth artifact is ./openapi.yml at the repo root (one flat
 * bundled file, no external $ref — decision #3). This script bridges the two.
 *
 * Run: node scripts/bundle-openapi.mjs   (usually via `npm run api:bundle`)
 */

import { copyFileSync, existsSync } from 'node:fs';
import { exit } from 'node:process';

const candidates = [
  'tsp-output/@typespec/openapi3/openapi.yaml',
  'tsp-output/@typespec/openapi3/openapi.yml',
  'tsp-output/openapi.yaml',
];

const src = candidates.find((p) => existsSync(p));
if (!src) {
  console.error('[bundle-openapi] ERROR: no emitter output found. Run `npm run api:compile` first.');
  console.error('[bundle-openapi] looked in:\n  - ' + candidates.join('\n  - '));
  exit(1);
}

copyFileSync(src, 'openapi.yml');
console.log(`[bundle-openapi] ${src} -> openapi.yml`);
