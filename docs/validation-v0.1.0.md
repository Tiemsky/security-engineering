# Validation report — v0.1.0 (in progress: phases A–D done)
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

## 5c. Not yet done (phases E–F)
Extended differential scenarios beyond the 23 above (e.g. per-rule coverage of all 8 signals), final release recommendation, tag decision.

## 6. Reproduce
`tests/run_all.sh` (47→48 tests) · `tests/smoke/opencode.sh <dir> [--with-model <m>]` (Docker) · `tests/smoke/claude.sh <dir>` · `tests/smoke/antigravity.sh <dir>` (real sessions, consume quota).
