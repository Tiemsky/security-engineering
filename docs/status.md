# Status — 2026-10-17 (v0.1.0 content; 122 tests collected, 33 differential scenarios; see validation report)
Test counts change with every addition: the authoritative number is the output of `tests/run_all.sh`. On 2026-10-17 without Docker: 122 run, 3 Docker-only skipped, all OK. The 71 and 82 quoted in older sections were true when written.
## Active testing — gate-driven pentest runner (added 2026-10-17)
`scripts/pentest-runner.py` runs ACTIVE checks (sends requests) only when `assessment-gate.py check` returns `allow`. 5 `active_read_only` modules: 4 stdlib (http-headers, cookie-flags, cors, tls) + external-tool modules `tls-scan` (testssl.sh) `http-scan` (nuclei: detection templates, no -dast, -ni, rate-limited), and the first `active_fuzzing` module `injection-fuzz` (sqlmap DETECTION only — refuses --dump/--os-shell/enumeration flags; gated: loopback-local, or explicit auth for staging, production_exception for prod; optional --confirm adds a benign proof step --banner/--current-user/--current-db, re-gated as sensitive_data_collection, dump/shell/enumeration still refused) — skipped if absent, tested with fake binaries, non-destructive (GET only; no exploitation/enforcement module; gate denies those classes); paced under the rate cap; loopback-first. 7 tests in `tests/pilot/test_pentest_runner.py` against a loopback fixture (finds missing headers/weak cookie/reflected CORS; proves NOTHING is sent when the gate denies; rate pacing; missing-gate denies) + a mutation check. Doc: `docs/ACTIVE-TESTING.md`. Not done: more external-tool modules (content-discovery/ffuf, authenticated crawl, etc.), active_fuzzing/active_authenticated modules, a real authorized target run.
## Generic read-only pilot (added after pilot A)
`scripts/audit-copy.sh` (committed-state copy via temporary index, secret files/shapes and symlinks excluded and listed, source never written), `scripts/extract-report-json.py`, `adapters/project/audit-prompt.txt.template`, `docs/PILOT-PROTOCOL.md`; 10 tests in `tests/pilot` (one mutation check: disabling the name-based removal fails a test). Not done: a second real project, repeated runs, independent verification of pilot A's remaining 16 findings. Staging/production execution tooling does not exist yet (next step).
## Environment-aware assessment (added after the validation)
Skill `environment-assessment` (13th skill) + `scripts/assessment-gate.py` + contracts `assessment-scope` / `assessment-report` + `core/assessment-coverage.yaml` + `core/assessment-quality-gate.md`. Agents gain the skill (orchestrator stage 0, auditor, architect, reviewer) and **no new permission**. `tests/assessment` (30 tests): classification, every gate rule, report validator, coverage topics, wiring, installed gate. Real sessions: 4 scenarios × Claude Code, Antigravity, OpenCode, all matching the gate after two fixes (see validation report §10). Not provided: a scanner or any tool that sends requests; automatic copy of the scope template; macOS/native Windows runs.

## Documentation (added after the validation)
`docs/USER-GUIDE.md`, `docs/COMMAND-REFERENCE.md`, `docs/EXAMPLES.md`, `docs/OWASP-COVERAGE.md` + `tests/docs/test_docs.py` (11 static checks: links/anchors, referenced paths, agent/skill names, status vocabulary, scenario and rule ids, no invented slash commands). They prove the documents are consistent with the repository, not that every described command works; each command carries its own EXECUTED/TESTED/DOCUMENTED/NOT-VERIFIED label. Suite: 82 tests green.
## Implemented AND executed in tests (47 tests, all green)
- 13 skills (frontmatter, 11 mandatory sections, references) · 5 agents → 15 generated native files, drift-checked · read-only/least-privilege boundaries asserted for all 3 tools.
- 8 event schemas + detection-rule schema: own validator + real `jsonschema` 4.23 (python:3.12 container) — samples, IPv4/IPv6, UTC, extras rejected.
- Policies: observe-only defaults, approval gates, TTL bounds, no sole-UA/geo/score blocking, redaction patterns (incl. UUID non-match; found and fixed a PAN-regex false positive).
- `install.sh` / `uninstall.sh` / `validate-installation.sh` in sandboxed HOMEs: dry-run, idempotency, config preservation, conflict+backup, version refusal, project pin, managed blocks, restore.
- `install.ps1`: executed under **PowerShell 7.4 on Linux** (Docker): dry-run, idempotency, preservation.
- Runtimes on **real Laravel 12.70 (PHP 8.4)** and **real NestJS 11.2 (Node 24)** in Docker: 9 shared scenarios × 2 frameworks — identical decisions, schema-valid events, no secret leakage, fail-open on store failure, expiry, XFF trust, IPv6 /64.
## Implemented, NOT exercised
- account_lock / session_revocation / challenge executors (NOT implemented: the engine always routes them to manual_review + pending_approval, tested), Redis store and workers (do not exist; state is per-process), queue-backed sinks, Laravel Policies / Nest Guards examples (guidance in skills only).
## Engine hardening (Phase D)
Rollback, retry/partial failure, malformed input, flood, expiry/window edges, redacted-id isolation, sink outage: 23 scenarios identical on Laravel and NestJS (see validation report §5b).
## Validated in real tool sessions (2026-10-16, see docs/validation-v0.1.0.md)
- Claude Code 2.1.301, OpenCode 1.19.2 (Docker), Antigravity CLI 1.3.4/1.4.0: agents + skills discovered; read-only boundaries held; defects found and fixed (OpenCode websearch, Antigravity tool names/delegation).
- Limitations: Claude reviewer Bash, no write-confirmation on Antigravity under always-proceed.
## Unverified
- Antigravity rules file (`.agents/rules`) effect on behaviour; implementer confirmation prompts in interactive OpenCode/Claude/Antigravity; OpenCode native-Windows path; `install.ps1` on native Windows PowerShell 5.1; macOS.
- Claude `--agent`-style use of the orchestrator.
## Next
Promote rules one at a time from observe; add Policy/Guard reference examples; add a queued sink; pin CI actions by SHA.
