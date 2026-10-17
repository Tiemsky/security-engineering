# Command reference

Only commands that exist in this repository's scripts, in the generated native agent files, or in the `--help` output of the installed CLIs are listed. Nothing here is an invented slash command, and **the three tools do not share one invocation syntax**.

**Status column** (first word is machine-checked by `tests/docs/test_docs.py`):
- `EXECUTED` — run for real, in the 2026-10-16 validation (evidence in [validation-v0.1.0.md](validation-v0.1.0.md)) or while writing this reference (marked "this session").
- `TESTED` — exercised by an automated test in `tests/` (which `tests/run_all.sh` runs).
- `DOCUMENTED` — shown by the tool's own `--help` or its documentation; **not run** by us.
- `NOT-VERIFIED` — not run, not confirmed.

Versions the "EXECUTED" claims refer to: Claude Code 2.1.301 (2.1.302 installed at writing time, `--help` read only), OpenCode 1.19.2 (Docker), `agy` 1.3.4 and 1.4.0. Tools auto-update; re-verify after an upgrade.

Four kinds of things are documented, kept apart on purpose:
1. [Repository shell commands](#1-repository-shell-commands) — scripts of this repo.
2. [CLI commands of the tools](#2-cli-commands-of-the-tools).
3. [Native agent invocation](#3-native-agent-invocation) — how to reach `security-*` agents in each tool.
4. [Natural-language prompts](#4-natural-language-prompts) — not commands; see [EXAMPLES.md](EXAMPLES.md).

---

## 1. Repository shell commands
Working directory: the repository root (`~/Apps/security-engineering`) unless noted.

### 1.1 Installation
| Command | Purpose | Prerequisites | Side effects | Expected output | Status |
|---|---|---|---|---|---|
| `scripts/install.sh --mode global --dry-run` | list every copy that a global install would do | bash, python3 | none (writes nothing) | `security-engineering 0.1.0 · … dry_run=1`, one line per action, `done: N action(s), 0 conflict(s)` | TESTED (`test_dry_run_writes_nothing`) |
| `scripts/install.sh --mode global [--tools claude,opencode,antigravity]` | install skills + agents for the current user; auto-detects tools if `--tools` omitted | tool config dir or binary present | writes `~/.claude/{skills,agents}`, `~/.config/opencode/…`, `~/.gemini/config/{skills,agents,rules}`, `~/.security-engineering/…`; managed block in global instruction files; never touches permission files | `done: N action(s)`; second run `0 action(s)`; exit 3 on conflict, 4 on version refusal | TESTED in sandboxed HOMEs (`tests/installer`); not run on the real HOME in the validation |
| `scripts/install.sh --mode global --claude-dir D --opencode-dir D --antigravity-dir D --shared-dir D` | redirect targets (also the way to target Windows-side configs from WSL) | — | as above, in the given dirs | as above | TESTED |
| `scripts/install.sh --mode project --project-dir DIR [--vendor-skills] [--tools …] [--framework F]` | version-pinned integration package in one application repo | `DIR` exists | creates `DIR/.security-engineering/`, `PROJECT_RULES.md`, agents in `.claude/.opencode/.agents`, managed blocks in `CLAUDE.md`/`AGENTS.md`, merges `opencode.json`; `--vendor-skills` also copies the 12 skills | `manifest: DIR/.security-engineering/manifest-project.json`, `done: 59 action(s), 0 conflict(s)` (59 observed this session with `--tools antigravity,claude --vendor-skills`) | TESTED; EXECUTED this session |
| `… --force` | overwrite conflicting files after backing them up | — | backup `*.bak.<UTC>` next to each overwritten file | — | TESTED |
| `… --allow-version-change` | permit downgrade / pin change | — | moves the pinned version | — | TESTED |
| `scripts/install.ps1 -Mode global\|project [-DryRun] [-ProjectDir D] …` | Windows installer | PowerShell 5.1+/7 | same as `install.sh` | same | TESTED under PowerShell 7.4 on Linux (Docker). Native Windows: **NOT-VERIFIED** |

### 1.2 Verification and removal
| Command | Purpose | Prerequisites | Side effects | Expected output | Status |
|---|---|---|---|---|---|
| `scripts/validate-installation.sh --mode global` | static check: installed files exist and match the manifest | prior install | none | OK, or a list of missing/modified files (non-zero) | TESTED (`test_validate_ok_and_detects_missing`). **Does not prove that a tool loaded the agents.** |
| `scripts/validate-installation.sh --mode project --project-dir DIR` | same for a project | — | none | same | TESTED |
| `scripts/uninstall.sh --mode global\|project [--project-dir DIR] [--dry-run] [--restore-backups]` | remove what the installer created | manifest present | removes unmodified managed files, keeps edited/pre-existing files, removes only the managed block from `CLAUDE.md`/`AGENTS.md`; `--restore-backups` restores `*.bak.*` | list of `remove`/`KEEP` lines | TESTED (uninstall matrix) |
| `scripts/uninstall.ps1 -Mode global\|project [-ProjectDir D]` | Windows equivalent | PowerShell | same | same | TESTED on PowerShell 7.4/Linux; native Windows NOT-VERIFIED |

### 1.3 Generation and policies
| Command | Purpose | Prerequisites | Side effects | Expected output | Status |
|---|---|---|---|---|---|
| `python3 scripts/build-adapters.py` | regenerate native agent files from `agents/*.md` + `agents/manifest.json` | python3 | rewrites `adapters/*/agents/*.md` (never edit those by hand) | — | EXECUTED |
| `python3 scripts/build-adapters.py --check` | exit 1 if generated files differ from sources | python3 | none | exit 0 when in sync | TESTED (`test_generated_adapters_are_up_to_date`, also first line of `run_all.sh`) |
| `python3 scripts/compile-policies.py [OUT_DIR]` | compile `policies/*.yaml` to JSON for the PHP/TS runtimes | python3 + PyYAML | writes JSON into `OUT_DIR` (default `policies/compiled`) | `compiled to <dir>` | EXECUTED (used by both integration runners) |

### 1.4 Tests
| Command | Purpose | Prerequisites | Side effects | Expected output | Status |
|---|---|---|---|---|---|
| `tests/run_all.sh` | adapter drift check + all unit/installer/contract/policy/agent/integration tests | python3, PyYAML, Docker (for the integration + PowerShell tests) | builds/uses Docker images `se-laravel-it`, `se-nest-it`; temp dirs | all `ok`: 71 tests on 2026-10-16 (fresh clone, rebuilt images); 122 collected on 2026-10-17 (119 run without Docker, 3 Docker-only skipped) — the output of the command is authoritative | EXECUTED |
| `tests/run_all.sh --no-docker` (or `SE_SKIP_DOCKER=1 tests/run_all.sh`) | same without Docker; the Docker tests are skipped **explicitly** | python3, PyYAML | none outside temp dirs | Docker-dependent tests reported as skipped | EXECUTED |
| `tests/integration/run_laravel.sh OUTDIR` | replay the shared scenarios in a real Laravel 12.70 app (PHP 8.4) | Docker | builds `se-laravel-it`; writes results into `OUTDIR` | per-scenario JSON | EXECUTED |
| `tests/integration/run_nestjs.sh OUTDIR` | same in a real NestJS 11.2 app (Node 24) | Docker | builds `se-nest-it` | per-scenario JSON | EXECUTED |
| `PYTHONPATH=tests/lib python3 -m unittest discover -s tests -p 'test_docs.py' -t tests -v` | documentation check: links and anchors, referenced paths, agent/skill names, status vocabulary, no invented slash commands | python3 + PyYAML | none | `OK` (11 tests) | EXECUTED when added; also part of `tests/run_all.sh` |

### 1.5 Smoke tests with real tool sessions (consume quota)
| Command | Purpose | Prerequisites | Side effects | Expected output | Status |
|---|---|---|---|---|---|
| `tests/smoke/claude.sh EVIDENCE_DIR [model=haiku]` | real Claude Code sessions in a throw-away repo (project scope) | `claude` logged in | budget cap `--max-budget-usd 0.40` per call; temp repo; `~/.claude` untouched | per-agent tool lists + PASS/FAIL lines for the write-permission probes | EXECUTED |
| `tests/smoke/opencode.sh EVIDENCE_DIR [--with-model provider/model]` | OpenCode discovery + permissions in Docker; with `--with-model` a real session | Docker; `--with-model`: network | phase 1 no model call; phase 2 sends **fictional** fixture prompts to that model's provider | agent list, skills JSON, session transcripts; `NOT VERIFIED` if the model call fails | EXECUTED |
| `tests/smoke/antigravity.sh EVIDENCE_DIR` | real `agy` sessions in a throw-away repo | `agy` logged in | **runs under your global `permission_mode`; with `always-proceed` the implementer writes without asking** (inside the temp repo); hashes `~/.gemini/config` before/after | before/after hashes identical | EXECUTED |

### 1.6 Environment and scope gate (deterministic; no model, contacts no target)
Needs python3 + PyYAML. In the toolkit repo the script is `scripts/assessment-gate.py`; the installer also copies it to `<shared>/scripts/assessment-gate.py` (project: `.security-engineering/shared/scripts/`, global: `~/.security-engineering/shared/scripts/`).
| Command | Purpose | Prerequisites | Side effects | Expected output | Status |
|---|---|---|---|---|---|
| `python3 scripts/assessment-gate.py classify SCOPE.yaml` | environment (local/staging/production/unknown), mode, confidence, reasons, rule ids from verifiable evidence | a scope file (`adapters/project/assessment-scope.yaml.template`, schema `contracts/assessment-scope.schema.json`) | none | JSON; exit 0, or exit 1 with schema problems | TESTED (`tests/assessment`, 13 scenarios) |
| `python3 scripts/assessment-gate.py check SCOPE.yaml --activity A [--target T] [--now ISO-UTC]` | decision `allow` / `needs_confirmation` / `deny` for one activity class against one target | as above | none | JSON with decision, rule ids, reasons, conditions; **exit 0 allow, 3 needs_confirmation, 1 deny**, 2 usage | TESTED (every rule exercised by a scenario; 6 injected defects detected) |
| `python3 scripts/assessment-gate.py validate-report REPORT.json` | schema + cross-field rules: coverage topics of the mode (`core/assessment-coverage.yaml`), PASS needs evidence, no PASS of operational controls from a code audit, summary consistent, no "secure" claim | a report (`contracts/assessment-report.schema.json`; example `tests/fixtures/assessment/report-code-only.json`) | none | JSON `valid` + `problems`; exit 0/1 | TESTED |
| `.security-engineering/shared/scripts/assessment-gate.py …` (installed copy) | same, inside an installed project | project or global install | none | same | TESTED (`python3 -I`, outside the repo checkout) on Linux; `install.ps1` copies it too (asserted in the PowerShell 7.4/Linux test); native Windows NOT-VERIFIED |
| `tests/smoke/assessment.sh claude\|antigravity\|opencode EVIDENCE_DIR [--with-model P/M]` | behavioural consistency: the same 4 fictional scenarios in a real session, answer compared with the gate | tool logged in (opencode: Docker + `--with-model`) | 4 short model calls; temp project; opencode sends the fictional prompts to that model's provider | PASS / FAIL / `NOT VERIFIED` per scenario | EXECUTED (4/4 on each of Claude Code haiku, Antigravity 1.4.0, OpenCode 1.19.2 free model, after fixes; see validation report §10) |

---

## 2. CLI commands of the tools
These are the tools' own commands, listed only where they matter to this toolkit.

### 2.1 Claude Code
| Command | Purpose | Working dir | Side effects | Status |
|---|---|---|---|---|
| `claude --agent security-auditor` | start an interactive session *as* that agent (tool list limited to the agent's `tools`) | the project | none until you ask for work | DOCUMENTED (`claude --help`: "--agent <agent>: Agent for the current session") |
| `claude -p "<prompt>" --agent <name> --model haiku --max-budget-usd 0.40 --no-session-persistence --output-format stream-json --verbose` | one non-interactive turn; the first `system/init` event lists tools, agents, skills | the project | model usage; a Bash/Edit call can be denied for lack of approval | EXECUTED (this is what `tests/smoke/claude.sh` runs) |
| `--allowedTools Edit` | pre-approve a tool for a session | — | removes the approval barrier for that tool | EXECUTED once, as the *control* showing that the implementer can write when approved |
| `/agents` (inside a session) | list/manage subagents | — | — | DOCUMENTED by Claude Code; **not run here** |
| `claude agents` | **background** agents (agent view); not a list of subagents | — | — | DOCUMENTED (`claude agents --help`, this session); not used by the toolkit |

### 2.2 OpenCode (Docker image with `opencode-ai@1.19.2`)
| Command | Purpose | Side effects | Status |
|---|---|---|---|
| `opencode agent list` | agents discovered in the project, with their effective permissions | none | EXECUTED |
| `opencode debug skill` | skills discovered (JSON) | none | EXECUTED |
| `opencode run --agent security-orchestrator --model <provider/model> --format json "<prompt>"` | headless turn with the primary agent | model usage; `ask` permissions cannot be answered headlessly → such writes are rejected | EXECUTED |
| `opencode run --agent <subagent>` | **do not use**: falls back to the default `build` agent, which can write | — | EXECUTED (this is the invalid test A1) |

### 2.3 Antigravity (`agy`)
| Command | Purpose | Side effects | Status |
|---|---|---|---|
| `agy --version` | version | none | EXECUTED (1.4.0 this session) |
| `agy -p "<prompt>" --agent security-orchestrator --effort low --print-timeout 250s --output-format stream-json` | headless turn with the main agent; delegates to subagents via `invoke_subagent` | model usage; honours your global `permission_mode` | EXECUTED |
| `agy agents` / `agy agent` | "List available agents" per `agy --help` | none | EXECUTED this session: **prints nothing**, outside and inside an installed project. Not usable as discovery proof |
| `--mode accept-edits\|auto\|plan` | execution mode for a session | `plan` may help keep a session non-writing | DOCUMENTED (`agy --help`); effect on the implementer **not verified** |
| `--dangerously-skip-permissions` | auto-approve all tool permission requests | removes every confirmation | DOCUMENTED; **never use with the security agents** |
| `--sandbox` | terminal restrictions | — | DOCUMENTED; not verified with these agents |

---

## 3. Native agent invocation
Agent files are generated into `adapters/<tool>/agents/` and copied by the installer. Same five names everywhere; **different mechanisms**:

| Tool | Select an agent | Delegation between agents | Status |
|---|---|---|---|
| Claude Code | `claude --agent security-<role>` (the session *is* that agent); or ask in natural language for a subagent | orchestrator has the `Agent` tool; delegation from `--agent security-orchestrator` | selection EXECUTED (`-p`); natural-language subagent use and orchestrator delegation **NOT-VERIFIED** |
| OpenCode | `opencode run --agent security-orchestrator …` (only the primary can be selected); other four are `mode: subagent` | `task` tool of the orchestrator; headless delegation to the implementer was rejected for lack of confirmation | selection EXECUTED; interactive TUI selection **NOT-VERIFIED** |
| Antigravity | `agy --agent security-orchestrator` (`mainAgent: true`); other four are `subagent: true` | `invoke_subagent` | EXECUTED (auditor + implementer delegation) |

Skills are invoked by naming them in the prompt, or are loaded automatically by the agent that lists them. There is no repository-defined slash command. Skill-to-agent assignment is in `agents/manifest.json`; `incident-response` is assigned to no agent.

## 4. Natural-language prompts
Prompts are *requests*, not commands: the same sentence may behave differently across tools and models. Ready-to-use prompts with scope, allowed/prohibited actions, evidence and acceptance criteria: [EXAMPLES.md](EXAMPLES.md).

## 1.7 Pilot helpers (read-only audit of any application)
| Command | Purpose | Prerequisites | Side effects | Expected output | Status |
|---|---|---|---|---|---|
| `scripts/audit-copy.sh --repo DIR --out NEW_DIR [--ref REV] [--dry-run]` | audit copy of the committed state without secret files or symlinks | bash, git | writes only `NEW_DIR` (must be empty and outside the repo); source `git status` compared before/after | `audit copy: … source repository unchanged`; exit 5 when secret-bearing files were tracked | TESTED (`tests/pilot`) |
| `scripts/extract-report-json.py REPORT.md [OUT.json]` | extract the last json block (assessment matrix) from a report | python3 | writes `OUT.json` | JSON; exit 1 if absent or invalid | TESTED |

## 1.8 Active testing (gate-driven; sends requests only when the gate allows)
Needs python3 + PyYAML. The runner calls `scripts/assessment-gate.py check` for each module and runs it only on `allow`. See [ACTIVE-TESTING.md](ACTIVE-TESTING.md).
| Command | Purpose | Prerequisites | Side effects | Expected output | Status |
|---|---|---|---|---|---|
| `scripts/pentest-runner.py list` | modules, their activity class and required binaries | python3 | none | one line per module | TESTED |
| `scripts/pentest-runner.py plan SCOPE.yaml --target URL [--now ISO-UTC]` | gate decision per module; **sends nothing** | a scope file | none | per-module `gate=allow/deny/needs_confirmation` | TESTED |
| `scripts/pentest-runner.py run SCOPE.yaml --target URL [--only m1,m2] [--out DIR] [--wordlist PATH] [--probes FILE] [--auth-header V] [--confirm] [--now ISO-UTC]` | run the allowed `active_read_only` modules (headers, cookies, CORS, TLS, `tls-scan` via `testssl.sh`, `http-scan` via `nuclei`, and the `active_fuzzing` `injection-fuzz` via `sqlmap` (detection only) when present and gate-allowed), paced under the rate cap | a scope file; a target you own or are authorized to test | requests to the target only when the gate allows; `--wordlist` feeds content-discovery; `--probes` + `$SE_AUTH_HEADER` drive idor-bola and priv-esc; `--confirm` adds the benign sensitive_data_collection proof step where a module supports it (re-gated); writes `DIR/pentest-run.jsonl` | `[ok]/[skip]` per module; exit 0 ran, 3 all denied (nothing sent), 1 a module errored | TESTED on a loopback fixture |
