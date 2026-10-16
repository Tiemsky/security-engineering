# Validation report — v0.1.0 (phases A–F complete)

## 0. Executive summary
v0.1.0 as first delivered (`a1161e9`/`30e97c7`) was **not** safe to release: real sessions and adversarial tests exposed **16 defects** (plus one invalid test of my own) (OpenCode read-only auditor could `websearch`; Antigravity agents had a non-existent tool name and the orchestrator could not delegate; uninstall deleted a user's pre-existing file; paths with spaces broke the manifest; enforcement state collapsed for redacted identifiers; a failed action left an attack unmitigated; unbounded memory and log amplification; …). All are fixed with regression tests. The validated content differs from what was delivered (contract 1.1.0, hardened engine, new scripts), so it should **not** be tagged as the original `v0.1.0`.
After fixes: **71 automated tests green from a fresh clone with all Docker images rebuilt from pinned versions** (PHP 8.4.26, Laravel 12.70.0, Node 24.21.0, NestJS 11.2.7, PowerShell 7.4), **33 differential scenarios × 2 frameworks identical**, real sessions in Claude Code 2.1.301, OpenCode 1.19.2 and Antigravity CLI 1.3.4/1.4.0.
**Recommendation: do not block, do not enable enforcement; authorise a staging pilot in read-only/observe mode** (§9).

Status legend: **PASS** (executed, evidence kept) · **FAIL** · **NOT VERIFIED** · tests labelled *real session* ran in the actual tool.

## 1. Baseline (Phase A, no file modified)
- Commit `a1161e9` (rewritten to `30e97c7` when the Co-Authored-By trailers were removed; content identical), VERSION 0.1.0, tree clean, no `v0.1.0` tag. 47 tests green from a fresh `git clone` (Docker images were cached → image rebuild not proven).
- Implicit dependencies: Docker + network for integration/PowerShell tests; PyYAML on host; floating image tags (`php:8.4`, `node:24`, `laravel ^12`, `powershell:latest`).
- Gaps vs. the Phase-2 brief: the runtime has **no Redis store and no worker/queue** (state is in-process), so "Redis/worker unavailable" is only simulable through the `storeFailure` hook; rollback, malformed events and partial-failure cases were untested.

## 2. Native loading and permissions (Phase B) — real sessions
| Tool (version) | Isolation | Discovery | Permissions observed | Status |
|---|---|---|---|---|
| Claude Code 2.1.301 | project scope in a temp repo; `~/.claude` untouched | `init` event of 5 real sessions lists all 5 `security-*` agents and 12 skills | architect/auditor tools = `Read,Grep,Glob`; auditor write attempt → file unchanged (no write tool). Reviewer = `Read,Bash`: a Bash redirect was **blocked only by the default approval prompt**. Implementer = `Read,Edit,Write,Bash`: unapproved write **denied** (`permission_denials`), same request with `Edit` pre-approved **succeeded** (control) | PASS, with limitation L1 |
| OpenCode 1.19.2 | Docker, config/data isolated, project scope | `opencode agent list` shows 5 agents (orchestrator primary, others subagent); `opencode debug skill` shows the 12 skills | effective rules match manifest (auditor/architect edit+bash deny; implementer ask; reviewer edit deny, bash ask). Real session (free model via the OpenCode provider): primary orchestrator could not write (no write tool); delegated auditor could not write (tools: glob/grep/read only); implementer write via headless delegation was rejected (file unchanged; the failure surfaced as "user rejected permission") | PASS, with limitations L2, L3 |
| Antigravity CLI 1.3.4 (re-run 1.4.0) | workspace scope (`.agents/`) in a temp repo; `~/.gemini/config` hashed before/after: **identical (260 files)** | session sees `security-*` subagents and the 12 skills; `init.agent` = `security-orchestrator` | orchestrator's declared tools = `view_file, grep_search, manage_task` (+`invoke_subagent` after fix); auditor via `invoke_subagent` has `view_file, grep_search, send_message, manage_task`; write attempt impossible, file unchanged. Implementer **wrote without any confirmation** (user's global `permission_mode: always-proceed`) | PASS (read-only), limitation L4 |
Tool-set statements for OpenCode/Antigravity come partly from the model's self-report of its tool declarations, corroborated by the absence of write/command tool events and by the unchanged witness file; Claude Code's come from the `init` event.

## 3. Defects found by real sessions (all fixed, with regression tests)
1. **OpenCode `websearch` was reachable by the read-only auditor** — OpenCode's implicit `"*": "allow"`. Fix: every OpenCode agent now starts with `"*": "deny"` then explicit allows (`test_opencode_agents_are_deny_by_default`). Re-verified: auditor tools no longer include `websearch`.
2. **Antigravity `edit_file` does not exist** in the CLI's tool catalog (real name `replace_file_content`) — a misspelled name can hang a subagent. Fixed; catalog captured in `tests/fixtures/antigravity-tool-catalog.json` and asserted by `test_antigravity_tool_names_exist_in_real_catalog`.
3. **Antigravity orchestrator could not delegate** (no `invoke_subagent`). Fixed; delegation to auditor and implementer verified.
4. A first OpenCode test was **invalid** (`--agent <subagent>` silently falls back to the default `build` agent, which can write). The smoke protocol now tests primary agents and delegation, and reports `NOT VERIFIED` when the model call fails (two runs failed with `APIError: Unable to connect`).

## 4. Limitations found (documented, not hidden)
- **L1** Claude reviewer has `Bash` (needed to run tests). It is read-only by instruction + default approval prompt, **not** technically; a user who pre-approves `Bash(*)` removes the barrier.
- **L2** OpenCode `ask` rules cannot be confirmed in headless `run`; interactive confirmation was not exercised.
- **L3** The OpenCode model call used a free third-party provider model; only fictional fixtures were sent.
- **L4** Antigravity gives agents no per-agent confirmation setting; with `always-proceed` the implementer writes unprompted. "Confirm before write" is therefore **not enforced by the adapter** on Antigravity.
- agy auto-updated 1.3.4 → 1.4.0 during the validation; results are tied to the versions above.

## 5. Installation / uninstall matrix (Phase C) — executed in temp dirs, real HOME untouched
| Case | Result |
|---|---|
| first install (global, project, project+vendored skills) · second install = 0 actions · dry-run (install and uninstall) writes nothing | PASS |
| conflict with user file → exit 3, content kept; `--force` → `.bak.<UTC>` backup; `uninstall --restore-backups` restores | PASS |
| upgrade 0.0.9→0.1.0: unmodified managed files updated, manifest version moved, validate OK; user-edited file kept + conflict | PASS |
| downgrade (global) and pin mismatch (project) refused, exit 4; `--allow-version-change` moves the pin | PASS |
| uninstall removes only unmodified managed files, keeps edited ones (`KEEP`), twice-safe, global/project manifests independent | PASS |
| foreign skill dir of the same name → conflict, user file intact | PASS |
| permission files (`settings.json`, Antigravity `config.json`) byte-identical after install | PASS |
| paths containing spaces/parentheses (HOME and project) | PASS after fix D3 |
| `install.ps1` + new `uninstall.ps1` on PowerShell 7.4/Linux (Docker): idempotent, preserve JSON/Markdown, uninstall restores original state | PASS |
| native Windows (5.1/7), ACLs, CRLF, locked files, OneDrive profile | **NOT EXECUTED** — protocol in `docs/windows-validation-protocol.md` |

### Defects found in Phase C (fixed, regression-tested)
- **D1** uninstall deleted a user's pre-existing file that merely had identical content (installer recorded it as owned). Now *adopted* and left unmanaged.
- **D2** uninstall left `$schema` added to a user's `opencode.json`, and left installer-created empty `CLAUDE.md`/`AGENTS.md`/`opencode.json`. The manifest now records `created` and `json_schema_added`.
- **D3** paths with spaces broke the manifest, validation and uninstall (word-splitting). Lists are now newline/tab-delimited.
- **D4** directory pruning (`rmdir -p`; same logic in the first PowerShell draft) could climb above the install location. Pruning now stops at tool roots.
- **D5** Windows had no uninstaller: `scripts/uninstall.ps1` added.

## 5b. Engine hardening and resilience (Phase D) — Laravel 12.70 and NestJS 11.2 in Docker, same inputs
23 shared scenarios (9 before + 14 new) × 2 frameworks = 46 runs, all schema-valid, redaction-checked and **identical across frameworks**.
| Requirement | Scenario | Result |
|---|---|---|
| Rollback executed, final state verified, idempotent, same-window repeats not re-blocked | rollback-flow | PASS |
| Partial failure / retry: failed action releases key, recovers when store recovers; gives up after 3; never blocks (fail-open); no partial state | retry-after-recovery, enforce-store-failure-fail-open | PASS |
| Duplicate / replayed event: no double execution; flood of 12 000 repeats → 1 decision, 1 notice, memory capped, state pruned | stuffing-observe, flood-bounded-memory | PASS |
| Malformed/unknown signals (10 shapes incl. zone-id IP, control chars, 300-char id, arrays) rejected, counted, health-logged once per reason | malformed-signals | PASS |
| Timestamps/expiry: window edge exclusive (no-trigger at 600 s, trigger at 599 s), block inactive exactly at `expires_at`, new window ⇒ new decision | window-edge-*, expiry-boundary, repeat-attack-new-window | PASS |
| Secrets masked (bearer-like id) and enforcement separate for redacted ids | secret-in-signal, redacted-identifier-no-collision | PASS |
| IP & trusted proxies: garbage/zone/mapped/non-canonical/untrusted-peer cases | client-ip-edge, client-ip-trust | PASS |
| observe / alert / enforce / manual_review separated | stuffing-observe, mode-alert, enforce-and-expire, shared-nat-no-block | PASS |
| `account_lock`, `session_revocation`, `challenge` never executed: manual_review + approval + `pending_approval`, nothing active | never-executes-risky-actions | PASS (policy-level only; no real lock/revocation exists) |
| Sink (log) outage does not break requests or enforcement | sink-failure-survives | PASS |
| Redis unavailable / worker unavailable | — | **NOT APPLICABLE to v0.1.0**: the runtime has no Redis store nor worker; state is per-process memory (documented in `adapters-runtime/generic/README.md`). Only the action-store outage hook is exercised |
**Mutation check**: re-introducing three defects (enforcement keyed on the redacted scope; no retry after failure; executor running non-executable actions) made the corresponding scenarios fail → the tests are not vacuous.
Laravel/NestJS divergences found and removed (not masked): IPv4-mapped IPv6 notation (`::ffff:a.b.c.d` vs hex groups) and zone-id acceptance differed in the TypeScript IP code; both now match PHP.
### Defects found in Phase D (all fixed)
- **D6** enforcement state was keyed on the *redacted* scope: two PAN-like identifiers (≥13 digits, e.g. phone numbers) collapsed into `[REDACTED]` and shared one block. Now keyed on the raw scope.
- **D7** a failed action consumed its idempotency key, leaving the attack unmitigated for the whole window. Now retried (≤ 3).
- **D8** one `skipped_duplicate` event per repeated request = log amplification under flood. Now one notice per key.
- **D9** windows/idempotency keys/shared-IP records were never pruned (unbounded memory); per-key list uncapped. Now pruned in `sweep()` and capped.
- **D10** sink exceptions propagated out of the engine into the request. Now swallowed and counted.
- **D11** malformed signals were not validated (could throw or be miscounted). Now rejected and counted.
- **D12** manual-review and allow-listed outcomes were mislabelled `skipped_observe_only`. Contract 1.1.0 adds `pending_approval` and `skipped_exception` (MINOR, 1.0.0 events stay valid).
### Limits that remain
Single-process memory only (restart loses windows/blocks; multi-instance counters diverge); no real account-lock/session-revocation/challenge executor; the engine trusts the caller for opaque identifiers.

## 5c. Differential coverage (Phase E)
33 scenarios, each executed on real Laravel and real NestJS with identical inputs; outputs must be schema-valid, redaction-clean and equal after normalisation (rule, decision, action, scope, mode, outcome status). **Every shipped rule (7) and every engine signal (8) has a scenario with a triggering case and a just-below-threshold or unmet-`min_distinct` case** (`rule-*.json`, guarded by `tests/integration/test_scenario_coverage.py`). Enforce mode is exercised with scoped blocking (other IPs unaffected), TTL expiry and recovery, and a shared-NAT honeypot hit that must stay `manual_review`.
Mutation checks (5 injected defects: redacted-scope keying, no retry after failure, executor without guard, threshold off-by-one, honeypot without shared-IP exception) each made the matching scenario fail.
**Divergences between Laravel and NestJS: none remain.** Two were found and fixed in the TypeScript IP code (IPv4-mapped notation, zone ids). Legitimate differences by design: none identified; framework-specific parts (middleware vs interceptor/filter) produce the same events.
Reproducibility: images and dependencies are now pinned (`tests/integration/docker/`), PowerShell test uses `7.4-ubuntu-22.04`.

## 6. Reproduce
`tests/run_all.sh` (71 tests) · `tests/smoke/opencode.sh <dir> [--with-model <m>]` (Docker) · `tests/smoke/claude.sh <dir>` · `tests/smoke/antigravity.sh <dir>` (real sessions, consume quota).

## 7. Vulnerabilities / defects discovered (all fixed unless noted)
| # | Where | Defect | Severity |
|---|---|---|---|
| B1 | OpenCode adapter | read-only agents inherited implicit `"*": "allow"` → `websearch` (network egress) reachable | High |
| B2 | Antigravity adapter | invalid tool name `edit_file` (can hang a subagent) | Medium |
| B3 | Antigravity adapter | orchestrator lacked `invoke_subagent` → could not delegate | Medium |
| C1 | uninstall | removed a user's pre-existing file that merely matched ours | **High** (data loss) |
| C2 | uninstall | left `$schema`/created empty files behind | Low |
| C3 | installer | paths with spaces broke manifest/validate/uninstall | Medium |
| C4 | uninstall | `rmdir -p` could prune above the install location | Medium |
| C5 | Windows | no uninstaller | Medium |
| D6 | engine | enforcement keyed on redacted scope → unrelated identifiers shared one block | **High** |
| D7 | engine | failed action consumed its idempotency key → attack unmitigated for the window | High |
| D8 | engine | one duplicate event per repeated request (log amplification) | Medium |
| D9 | engine | unbounded in-memory windows/keys | Medium (DoS) |
| D10 | engine | sink exception propagated into the request | Medium |
| D11 | engine | malformed signals unvalidated | Medium |
| D12 | engine/contract | manual-review/allowlisted outcomes mislabelled | Low |
| T1 | TS runtime | IPv4-mapped / zone-id handling differed from PHP | Medium |
| A1 | tests | first OpenCode smoke test invalid (`--agent` on a subagent falls back to `build`) | process |
Not defects but documented: Claude `security-reviewer` has `Bash` (read-only by instruction + approval, L1); Antigravity cannot enforce confirm-before-write (L4).

## 8. Unresolved limitations
1. Native Windows (PowerShell 5.1/7, ACLs, CRLF, locked files): **not executed** — protocol in `docs/windows-validation-protocol.md`. macOS not tested.
2. Interactive confirmation prompts were not exercised in any tool (only non-interactive/headless behaviour); Antigravity gives no per-agent confirmation control (L4); Claude reviewer Bash (L1).
3. Engine state is per-process memory: no Redis/worker; restart loses windows and active blocks; multi-instance counters diverge. No real account-lock, session-revocation or challenge executor (always `manual_review`).
4. No pilot on a real Laravel project yet (pilots A/B/C not run).
5. OpenCode/Antigravity tool lists partly rely on model self-report (corroborated by absence of write events); free third-party model used for OpenCode runs (fictional fixtures only).
6. Tool CLIs auto-update (agy 1.3.4→1.4.0 during validation); results are version-bound.
7. CI workflow has never run on a hosted runner; actions are not SHA-pinned.

## 9. Release criteria and recommendation
| Criterion | Status |
|---|---|
| Tests green from a clean state (fresh clone, rebuilt pinned images) | **MET** (71/71) |
| Three tools load the agents/skills (real sessions) | **MET** (discovery + roles); interactive UI not exercised |
| Permissions actually enforced | **MET with limitations** (L1, L4; headless only) |
| Install / upgrade / uninstall validated, backups verified | **MET** on Linux & PowerShell 7/Linux; **NOT MET** on native Windows/macOS |
| Rollback and failure scenarios, final state verified | **MET** for the in-memory engine; Redis/worker N/A |
| Laravel pilot in observe mode | **NOT MET** (not run) |
| Report with residual risks and justified decision | **MET** (this document) |
5 of 7 met, 1 partial, 1 not met.
**Decision: authorise a staging pilot in read-only / observe-only mode; keep enforcement blocked; do not publish a stable tag yet.**
- Allowed now: pilot A (read-only audit of a test Laravel project) and pilot C (runtime wired in `observe`, test events only).
- Blocked: any `enforce`/automatic blocking on real traffic, account lock / session revocation, global install on machines used for production work until the Windows/macOS protocol is run.
- Before a stable tag: run the Windows protocol, run pilots A–C and record results here, decide on Redis-backed state if multi-instance, then tag. Because the validated content differs from the first delivery, tag it as **`v0.1.1`** (or a `-rc` of it) rather than `v0.1.0`; `VERSION` is still `0.1.0` pending that decision.
