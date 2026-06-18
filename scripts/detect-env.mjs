/**
 * scripts/detect-env.mjs
 *
 * Detects the local environment and writes .claude/memory/env-detect.json.
 *
 * Run: node scripts/detect-env.mjs
 *
 * IMPORTANT: Do NOT hand-edit the output file. It is regenerated on every
 * session start by the SessionStart hook (scripts/session-start.sh) and is
 * used as the source of truth by /doctor and /bootstrap to gate unsafe
 * operations. Fabricated values silently bypass safety checks.
 *
 * NOTE: This script stores NO secrets. It records only the *kind* of a GitHub
 * PAT (fine-grained vs classic) — never the token value itself.
 */

import { execSync, spawnSync } from 'node:child_process';
import { mkdirSync, readFileSync, writeFileSync, existsSync } from 'node:fs';
import { platform } from 'node:os';
import { cwd, env, execPath, version } from 'node:process';

function hasBin(name) {
  try {
    return spawnSync('sh', ['-c', `command -v ${name}`], { timeout: 5000 }).status === 0;
  } catch {
    return false;
  }
}

function binVersion(bin, flag = '--version') {
  try {
    const r = spawnSync(bin, [flag], { encoding: 'utf8', timeout: 8000 });
    if (r.status === 0 && r.stdout) return r.stdout.split('\n')[0].trim();
    return null;
  } catch {
    return null;
  }
}

// --- Platform ---
const rawPlatform = platform();
let detectedPlatform;
if (rawPlatform === 'win32') detectedPlatform = 'windows';
else if (rawPlatform === 'darwin') detectedPlatform = 'darwin';
else detectedPlatform = 'linux';

let isWsl2 = false;
try {
  if (existsSync('/proc/version')) {
    isWsl2 = readFileSync('/proc/version', 'utf8').toLowerCase().includes('microsoft');
  }
} catch { /* ignore */ }

// --- Platform tier (supported / best-effort / unsupported) ---
// supported   : linux / macOS / WSL2 — fully tested; OS-level Bash-tool sandbox available.
// best-effort : native Windows WITH a POSIX bash (Git Bash) + git on PATH — gate scripts run
//               through Git Bash, but there is NO OS-level Bash-tool sandbox; less tested.
// unsupported : native Windows WITHOUT bash, or any platform we cannot run the bash gates on.
let platformTier;
let sandboxAvailable;
if (detectedPlatform === 'linux' || detectedPlatform === 'darwin') {
  platformTier = 'supported';
  sandboxAvailable = true;
} else if (detectedPlatform === 'windows') {
  const hasBashBin = hasBin('bash');
  const hasGitBin = hasBin('git');
  platformTier = hasBashBin && hasGitBin ? 'best-effort' : 'unsupported';
  sandboxAvailable = false;
} else {
  platformTier = 'unsupported';
  sandboxAvailable = false;
}
// Backward-compat boolean (coarse gate): anything not 'unsupported' passes.
const platformSupported = platformTier !== 'unsupported';

// --- Wrong-runner heuristic (WSL2 user launched Windows node.exe via PATH interop) ---
let wrongRunnerSuspected = false;
try {
  const execPathLower = execPath.toLowerCase();
  const windowsPathLike =
    /^[a-z]:[\\\/]/.test(execPathLower) || execPathLower.startsWith('/mnt/c/');
  if (detectedPlatform === 'windows' && isWsl2) wrongRunnerSuspected = true;
  else if (isWsl2 && windowsPathLike) wrongRunnerSuspected = true;
} catch { /* ignore */ }

// --- Shell ---
const shellEnv = env['SHELL'] || '';
const shell = shellEnv ? shellEnv.split('/').pop() : 'unknown';

// --- Node ---
const nodeParts = version.replace('v', '').split('.');
const nodeMajor = parseInt(nodeParts[0], 10);
const nodeMinor = parseInt(nodeParts[1] || '0', 10);
const nodeSupported = nodeMajor > 20 || (nodeMajor === 20 && nodeMinor >= 19);

// --- Tools ---
const tools = {};
const toolVersions = {};
const toolList = ['git', 'gh', 'node', 'npm', 'npx', 'oasdiff', 'docker'];
for (const t of toolList) {
  tools[t] = hasBin(t);
  toolVersions[t] = null;
}
if (tools.git) toolVersions.git = binVersion('git');
if (tools.gh) toolVersions.gh = binVersion('gh');
if (tools.node) toolVersions.node = version;
if (tools.npm) toolVersions.npm = binVersion('npm');
if (tools.npx) toolVersions.npx = binVersion('npx');
if (tools.oasdiff) toolVersions.oasdiff = binVersion('oasdiff');
if (tools.docker) toolVersions.docker = binVersion('docker');

// --- GitHub auth (kind of PAT only; never the token) ---
let ghAuthenticated = false;
let ghPatKind = null;
try {
  if (tools.gh) {
    ghAuthenticated = spawnSync('gh', ['auth', 'status'], { timeout: 10000 }).status === 0;
    const tokenFromEnv = env['GITHUB_PERSONAL_ACCESS_TOKEN'] || env['GITHUB_TOKEN'] || '';
    if (tokenFromEnv.startsWith('github_pat_')) ghPatKind = 'fine-grained';
    else if (tokenFromEnv.startsWith('ghp_')) ghPatKind = 'classic';
    else {
      try {
        const tokenOut = execSync('gh auth token', {
          encoding: 'utf8', stdio: ['pipe', 'pipe', 'pipe'], timeout: 8000,
        }).trim();
        const prefix = tokenOut.slice(0, 12);
        if (prefix.startsWith('github_pat_')) ghPatKind = 'fine-grained';
        else if (prefix.startsWith('ghp_')) ghPatKind = 'classic';
        else if (tokenOut.length > 0) ghPatKind = 'unknown';
      } catch {
        ghPatKind = ghAuthenticated ? 'unknown' : null;
      }
    }
  }
} catch { /* ignore */ }

// --- Assemble + write ---
const result = {
  schema_version: 1,
  generated_at: new Date().toISOString(),
  platform: detectedPlatform,
  is_wsl2: isWsl2,
  platform_tier: platformTier,
  platform_supported: platformSupported,
  sandbox_available: sandboxAvailable,
  shell,
  node: { version, major: nodeMajor, execPath },
  node_supported: nodeSupported,
  wrong_runner_suspected: wrongRunnerSuspected,
  cwd: cwd(),
  tools,
  tool_versions: toolVersions,
  gh: { authenticated: ghAuthenticated, pat_kind: ghPatKind },
};

const outDir = '.claude/memory';
const outFile = `${outDir}/env-detect.json`;
try {
  mkdirSync(outDir, { recursive: true });
  writeFileSync(outFile, JSON.stringify(result, null, 2) + '\n', 'utf8');
} catch (err) {
  console.error(`[detect-env] ERROR: could not write ${outFile}: ${err.message}`);
}

const tierLabel = {
  supported: 'SUPPORTED',
  'best-effort': 'BEST-EFFORT (native Windows / Git Bash; no sandbox)',
  unsupported: 'UNSUPPORTED (install WSL2, or Git Bash on native Windows)',
};
const supportedStr = tierLabel[platformTier] || 'UNKNOWN';
const nodeStr = nodeSupported ? `Node ${version} OK` : `Node ${version} TOO OLD (need 20.19+)`;
const wslStr = isWsl2 ? ' [WSL2]' : '';
const wrongStr = wrongRunnerSuspected ? ' WRONG RUNNER SUSPECTED' : '';
console.log(`[detect-env] platform=${detectedPlatform}${wslStr} ${supportedStr} | ${nodeStr}${wrongStr} | written ${outFile}`);
