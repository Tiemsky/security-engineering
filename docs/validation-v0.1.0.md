# Validation report — v0.1.0 (in progress: phases A, B and C done)
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

## 5b. Not yet done (phases D–F)
Engine rollback/partial-failure/malformed-event tests, extended Laravel/NestJS differential scenarios, `account_lock`/`session_revocation` status, release recommendation.

## 6. Reproduce
`tests/run_all.sh` (47→48 tests) · `tests/smoke/opencode.sh <dir> [--with-model <m>]` (Docker) · `tests/smoke/claude.sh <dir>` · `tests/smoke/antigravity.sh <dir>` (real sessions, consume quota).
