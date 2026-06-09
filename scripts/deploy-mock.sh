#!/usr/bin/env bash
# scripts/deploy-mock.sh
#
# GATE: build + push the Prism static mock Docker image to ghcr.io, then
# print the exact `docker run` command to execute on the VPS.
#
# The agent NEVER SSH-es into the VPS. This script runs locally. The printed
# VPS command is the deliverable — the user runs it manually on the server.
#
# Usage:
#   bash scripts/deploy-mock.sh --ip <VPS_IP>
#   bash scripts/deploy-mock.sh --ip <VPS_IP> --port 4010 --tag v0.3.0
#   bash scripts/deploy-mock.sh --dry-run --ip 1.2.3.4
#
# Flags:
#   --ip <IP>        VPS IP address (required; also accepts VPS_IP env var)
#   --port <PORT>    port to expose (default: PRISM_PORT env var → 4010)
#   --owner <owner>  GitHub owner/org (auto-detected from git remote)
#   --repo <repo>    repo slug (auto-detected from git remote)
#   --tag <tag>      Docker image tag (auto-detected from latest v* git tag)
#   --dry-run        Print planned commands without executing docker commands;
#                    still prints the VPS command block (that is always emitted)
#
# Requirements:
#   - docker on PATH
#   - GITHUB_PERSONAL_ACCESS_TOKEN set in the environment (or .env loaded)
#   - openapi.yml present (built by: npm run api:compile && npm run api:bundle)
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT" || exit 1

# ---------------------------------------------------------------------------
# Load .env if present (so GITHUB_PERSONAL_ACCESS_TOKEN / PRISM_PORT are
# available without the user having to manually export them first)
# ---------------------------------------------------------------------------
if [[ -f "$ROOT/.env" ]]; then
  # Only export lines that look like KEY=value (skip comments and blanks)
  set -a
  # shellcheck disable=SC1091
  source <(grep -E '^[A-Za-z_][A-Za-z0-9_]*=' "$ROOT/.env") 2>/dev/null || true
  set +a
fi

# ---------------------------------------------------------------------------
# Parse flags
# ---------------------------------------------------------------------------
DRY_RUN=false
VPS_IP="${VPS_IP:-}"
PORT="${PRISM_PORT:-4010}"
ARG_OWNER=""
ARG_REPO=""
ARG_TAG=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --dry-run)     DRY_RUN=true;          shift ;;
    --ip)          VPS_IP="$2";           shift 2 ;;
    --ip=*)        VPS_IP="${1#--ip=}";   shift ;;
    --port)        PORT="$2";             shift 2 ;;
    --port=*)      PORT="${1#--port=}";   shift ;;
    --owner)       ARG_OWNER="$2";        shift 2 ;;
    --owner=*)     ARG_OWNER="${1#--owner=}"; shift ;;
    --repo)        ARG_REPO="$2";         shift 2 ;;
    --repo=*)      ARG_REPO="${1#--repo=}"; shift ;;
    --tag)         ARG_TAG="$2";          shift 2 ;;
    --tag=*)       ARG_TAG="${1#--tag=}"; shift ;;
    *) echo "[deploy] ERROR: Unknown flag: $1" >&2; exit 1 ;;
  esac
done

# ---------------------------------------------------------------------------
# Validate required: --ip
# ---------------------------------------------------------------------------
if [[ -z "${GITHUB_PERSONAL_ACCESS_TOKEN:-}" ]]; then
  echo "[deploy] FAIL: GITHUB_PERSONAL_ACCESS_TOKEN is not set. Set it in .env or export it." >&2
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "[deploy] FAIL: docker not found on PATH. Install Docker first." >&2
  exit 1
fi

if [[ -z "$VPS_IP" ]]; then
  echo "[deploy] ERROR: --ip <IP> is required (or set the VPS_IP environment variable)." >&2
  echo "[deploy] Usage: bash scripts/deploy-mock.sh --ip <VPS_IP> [--port <PORT>] [--dry-run]" >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Auto-detect owner and repo from git remote origin
# (same sed patterns as scripts/personalize.sh lines 79-89)
# ---------------------------------------------------------------------------
REMOTE_URL="$(git remote get-url origin 2>/dev/null || true)"
DETECTED_OWNER=""
DETECTED_SLUG=""

if [[ -n "$REMOTE_URL" ]]; then
  # Handles https://github.com/OWNER/SLUG[.git] and git@github.com:OWNER/SLUG[.git]
  DETECTED_OWNER="$(echo "$REMOTE_URL" | sed -E \
    's|https://[^/]+/([^/]+)/.*|\1|; t done
     s|git@[^:]+:([^/]+)/.*|\1|
     :done')"
  DETECTED_SLUG="$(echo "$REMOTE_URL" | sed -E \
    's|https://[^/]+/[^/]+/([^/]+)$|\1|; t done
     s|git@[^:]+:[^/]+/([^/]+)$|\1|
     :done')"
  # Strip trailing .git suffix (present in clone URLs)
  DETECTED_SLUG="${DETECTED_SLUG%.git}"
fi

OWNER="${ARG_OWNER:-${DETECTED_OWNER}}"
REPO="${ARG_REPO:-${DETECTED_SLUG}}"

# Fallback: use directory name for repo slug
if [[ -z "$REPO" ]]; then
  REPO="$(basename "$ROOT")"
fi
if [[ -z "$OWNER" ]]; then
  echo "[deploy] ERROR: Could not detect GitHub owner from git remote. Use --owner <owner>." >&2
  exit 1
fi

# ---------------------------------------------------------------------------
# Auto-detect tag from latest v* git tag; fallback to 'latest'
# ---------------------------------------------------------------------------
DETECTED_TAG="$(git tag --list 'v*' --sort=-version:refname | head -n1)"
TAG="${ARG_TAG:-${DETECTED_TAG:-latest}}"

# ---------------------------------------------------------------------------
# Derived values
# ---------------------------------------------------------------------------
IMAGE="ghcr.io/${OWNER}/${REPO}-mock:${TAG}"
CONTAINER_NAME="${REPO}-mock"

# ---------------------------------------------------------------------------
# Run check_ready.sh (skip in --dry-run mode)
# ---------------------------------------------------------------------------
if [[ "$DRY_RUN" == "true" ]]; then
  echo "[deploy] DRY-RUN: would run check_ready.sh"
else
  echo "[deploy] --- running check_ready.sh ---"
  if ! bash "$ROOT/scripts/check_ready.sh"; then
    echo "[deploy] FAIL: contract is not ready. Run: npm run ready" >&2
    exit 1
  fi
fi

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
echo "[deploy] image : ${IMAGE}"
echo "[deploy] port  : ${PORT}"
echo "[deploy] VPS   : ${VPS_IP}:${PORT}"

# ---------------------------------------------------------------------------
# docker build
# ---------------------------------------------------------------------------
if [[ "$DRY_RUN" == "true" ]]; then
  echo "[deploy] DRY-RUN: would run: docker build -t ${IMAGE} ."
else
  echo "[deploy] --- building image ---"
  if ! docker build -t "${IMAGE}" .; then
    echo "[deploy] FAIL: docker build failed." >&2
    exit 1
  fi
fi

# ---------------------------------------------------------------------------
# docker login ghcr.io
# ---------------------------------------------------------------------------
if [[ "$DRY_RUN" == "true" ]]; then
  echo "[deploy] DRY-RUN: would run: docker login ghcr.io -u ${OWNER} --password-stdin <<< \"\$GITHUB_PERSONAL_ACCESS_TOKEN\""
else
  echo "[deploy] --- logging in to ghcr.io ---"
  docker login ghcr.io -u "${OWNER}" --password-stdin <<< "$GITHUB_PERSONAL_ACCESS_TOKEN"
fi

# ---------------------------------------------------------------------------
# docker push
# ---------------------------------------------------------------------------
if [[ "$DRY_RUN" == "true" ]]; then
  echo "[deploy] DRY-RUN: would run: docker push ${IMAGE}"
else
  echo "[deploy] --- pushing image ---"
  if ! docker push "${IMAGE}"; then
    echo "[deploy] FAIL: docker push failed." >&2
    exit 1
  fi
fi

# ---------------------------------------------------------------------------
# VPS command block (ALWAYS printed — this is the deliverable)
# ---------------------------------------------------------------------------
echo ""
echo "[deploy] ─────────────────────────────────────────────────────────"
echo "[deploy] VPS command (run on your server):"
echo ""
echo "  docker pull ${IMAGE}"
echo "  docker stop ${CONTAINER_NAME} 2>/dev/null || true"
echo "  docker rm   ${CONTAINER_NAME} 2>/dev/null || true"
echo "  docker run -d --restart unless-stopped \\"
echo "    --name ${CONTAINER_NAME} \\"
echo "    -e PRISM_PORT=${PORT} \\"
echo "    -p ${PORT}:${PORT} \\"
echo "    ${IMAGE}"
echo ""
echo "[deploy] Base URL: http://${VPS_IP}:${PORT}"
echo ""
echo "[deploy] NOTE: if the ghcr.io package is private, the VPS needs:"
echo "[deploy]   docker login ghcr.io -u <username> --password-stdin <<< \"\$GITHUB_PERSONAL_ACCESS_TOKEN\""
echo "[deploy] ─────────────────────────────────────────────────────────"

# ---------------------------------------------------------------------------
# Final status
# ---------------------------------------------------------------------------
if [[ "$DRY_RUN" == "true" ]]; then
  echo "[deploy] DRY-RUN complete. No docker commands were executed."
else
  echo "[deploy] OK: image pushed. Run the VPS command above to start the mock."
fi
