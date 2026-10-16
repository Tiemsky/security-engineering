# Status — 2026-10-16 (v0.1.0 content, post-validation: 71 tests, 33 differential scenarios; see validation report)
## Implemented AND executed in tests (47 tests, all green)
- 12 skills (frontmatter, 11 mandatory sections, references) · 5 agents → 15 generated native files, drift-checked · read-only/least-privilege boundaries asserted for all 3 tools.
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
