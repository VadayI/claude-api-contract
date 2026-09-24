# React workflow-equivalent check catalog

`templates/ai/checks/react.json` maps every check in the current Frontend CI
quality and E2E jobs to 15 stable runner IDs. Checkout, Node setup, dependency
installation, browser availability, and report upload remain explicit
orchestration/reporting mappings rather than invented PASS-producing checks.

Run only an exact committed candidate and ancestor base. Network is disabled by
default and must be deliberately enabled for npm advisory and pinned-contract
checks:

```text
python scripts/ai/runner.py --repository . --candidate FULL_CANDIDATE_SHA --base FULL_BASE_SHA --event pull_request --network allowed --catalog templates/ai/checks/react.json --output .ai-runtime/results/react.json
```

The catalog covers npm audit, typecheck, lint, file-size, stubs, feature READMEs,
API type drift, pinned contract synchronization, living-plan/routes/guides
policies, unit coverage, production build, bundle budgets, and Playwright E2E.
Each npm check receives a private exact-lockfile capsule. Generated API types are
compared to committed candidate bytes; coverage, build and Playwright reports are
declared artifacts; TypeScript build metadata is declared transient output.

`scripts/ai/react_gate.py` contains the reviewed multi-command behavior:

- npm vulnerabilities are failures; advisory-service/transport outages are
  `NOT_VERIFIED` (exit 75), never false PASS;
- contract sync uses only `contract.lock.json`, the committed OpenAPI bytes and a
  bounded public HTTPS fetch. It never reads `.env` or credentials;
- plan/routes/guides receive immutable `{run_context}` and `{base_export}` argv
  values from the runner. There is no `origin/main`, `HEAD~1`, environment, fetch,
  or working-tree fallback;
- bundle size performs build and strict deterministic gzip-budget validation in
  the same private capsule, without a fail-open shell/toolchain dependency,
  because separate runner checks never share candidate mutations;
- E2E supervises a loopback-only Vite server, health check, Chromium Playwright
  journeys, checked-in axe accessibility assertions, HTML report, and process-tree
  cleanup. A missing browser is `NOT_VERIFIED`; test/a11y failures remain failures.

The runner declaration is policy evidence, not packet-level sandboxing. External
commands start only when both the catalog and `--network allowed` permit them.
Loopback E2E declares `network_access: loopback`. Missing tools, browser binaries,
network inputs, artifacts, or exact base/context remain `NOT_VERIFIED` and produce
a nonzero runner outcome.

The vendored core receipt remains `pin_status: development` until the exact
contract runner commit is merged upstream. P06 owns CI mode selection and workflow
materialization; it does not replace these P05 gate implementations. P13 owns full
install/adopt/update rollback and interruption acceptance.
