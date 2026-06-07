# Plan 0003 — Release v0.1.0

## Goal / scope
Випустити перший git-тег контракту `v0.1.0`: встановити oasdiff, підготувати release-prep PR, пройти CI (5 гейтів), тегувати `main`, створити GitHub Release. Не змінює контракт — лише документація та metadata.

## Steps (files)
- Env: встановити oasdiff v1.18.4 у `~/.local/bin`.
- docs-writer — `CHANGELOG.md` (Unreleased→0.1.0), `docs/api/INDEX.md` (зняти «unreleased»), `package.json` (0.0.0→0.1.0).
- PR #3 `chore/release-v0.1.0` → CI green → merged.
- git tag `v0.1.0` + push; `gh release create`.

## Risks
- `scripts/check_breaking.sh` вимагає oasdiff перед SKIP-гілкою → Крок 1 обов'язковий.
- Drift при recompile → перевіряємо, що `openapi.yml` не змінився після bundle.
- Тег пушимо окремо від `main` (PR-only правило).

## Execution log
- phase done: env — oasdiff 1.18.4 встановлено, ~/.bashrc оновлено, env-detect.json оновлено.
- phase done: docs-writer — CHANGELOG промоут, INDEX unreleased знято, package.json 0.1.0.
- phase done: gates — validate GREEN (drift+lint+examples); breaking SKIP (перший тег).
- phase done: PR #3 merged (CI 38 с); git tag v0.1.0 pushed; GitHub Release опублікований.
