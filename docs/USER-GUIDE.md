# User guide

How to install, discover, invoke and verify the security agents and skills in **Claude Code**, **OpenCode** and **Google Antigravity** (`agy`).

> This toolkit is an *engineering assistant*, not an automatic guarantee of security. Skills tell an agent what to inspect and implement; only the code that lands in your application, and the tests that you run, secure it. What each part is verified to do is stated in [status.md](status.md) and [validation-v0.1.0.md](validation-v0.1.0.md). Control-by-control coverage: [OWASP-COVERAGE.md](OWASP-COVERAGE.md).

Companion documents: [COMMAND-REFERENCE.md](COMMAND-REFERENCE.md) (every command and whether it was executed), [EXAMPLES.md](EXAMPLES.md) (copy-ready prompts), [installation.md](installation.md), [project-integration.md](project-integration.md).

Verification labels used below: **EXECUTED** (run, evidence in the validation report or in this session) · **TESTED** (covered by an automated test in `tests/`) · **DOCUMENTED** (taken from the tool's help/docs, not run here) · **NOT VERIFIED**.

---

## 1. Prerequisites and supported environments

| Item | Requirement | Status |
|---|---|---|
| Linux, WSL | bash + python3 (installer); PyYAML only to run the test-suite | EXECUTED / TESTED (Linux) |
| macOS | same as Linux | **NOT VERIFIED** (never run) |
| Windows | PowerShell 5.1+/7 (`install.ps1`, `uninstall.ps1`) | TESTED under PowerShell 7.4 on Linux (Docker); **native Windows NOT EXECUTED** — see [windows-validation-protocol.md](windows-validation-protocol.md) |
| Docker | only to run the Laravel/NestJS/OpenCode/PowerShell integration tests | EXECUTED |
| Claude Code | validated on 2.1.301 (2.1.302 present when this guide was written; not re-run) | EXECUTED (real sessions, `-p`) |
| OpenCode | validated on 1.19.2, in Docker | EXECUTED (real sessions, headless) |
| Antigravity CLI `agy` | validated on 1.3.4 and 1.4.0 | EXECUTED (real sessions, headless) |

The tools auto-update; results are bound to the versions above. Nothing in this repository needs admin rights, and the installer copies files (no symlinks).

Not needed: production access, real credentials, real user data. Never run any of this guide against production.

## 2. Install

Run from the central repository (`~/Apps/security-engineering`). Always start with `--dry-run`; it writes nothing.

### 2.1 Global (your user, all projects)
```bash
scripts/install.sh --mode global --dry-run
scripts/install.sh --mode global --tools claude,opencode,antigravity   # or omit --tools to auto-detect
scripts/validate-installation.sh --mode global
```
Installs the 13 skills and 5 agents into each tool's user directory (`~/.claude`, `~/.config/opencode`, `~/.gemini/config`) plus `~/.security-engineering/shared` and a manifest. Existing files that differ are reported as conflicts (exit 3) and left untouched unless you pass `--force`, which backs them up first (`*.bak.<UTC>`). Permission/settings files are never modified. Details: [installation.md](installation.md).

Antigravity caveat: only a small targeted set goes into `~/.gemini/config/skills`. Back up `~/.gemini/config` before the first global install on a machine you rely on.

### 2.2 Project (recommended for a team; version-pinned)
```bash
scripts/install.sh --mode project --project-dir ~/dev/my-app --dry-run
scripts/install.sh --mode project --project-dir ~/dev/my-app --vendor-skills
scripts/validate-installation.sh --mode project --project-dir ~/dev/my-app
```
Creates in the application repository (commit these): `.security-engineering/config.yaml` (pinned version, framework, `mode: observe`), `PROJECT_RULES.md`, managed blocks in `CLAUDE.md` and `AGENTS.md`, `opencode.json` instructions, native agents in `.claude/agents`, `.opencode/agents`, `.agents/agents`, and — with `--vendor-skills` — the skills in `.claude/skills`, `.opencode/skills`, `.agents/skills`.

Without `--vendor-skills` a project install provides agents that name skills which must come from a global install. Use `--vendor-skills` for a self-contained project.

After installing, fill in `.security-engineering/config.yaml`: `framework`, `auth.mechanism`, `auth.authorization`, `trusted_proxies`, and `verify_commands` (the test and audit commands the agents may run — local/CI only).

## 3. Verify installation and agent discovery

`validate-installation.sh` is a **static** check (files present and unmodified). It does not prove a tool loaded the agents. Check discovery in each tool:

| Tool | Command | What it shows | Status |
|---|---|---|---|
| Claude Code | `claude --agent security-auditor -p "Reply with exactly: OK" --output-format stream-json --verbose` in the project; the first `system/init` event lists `agents` and `skills` | 5 `security-*` agents + skills | EXECUTED |
| Claude Code (interactive) | `/agents` | agent list | DOCUMENTED only; not run here |
| OpenCode | `opencode agent list` and `opencode debug skill` | 5 agents (orchestrator = primary, others = subagent) and 13 skills | EXECUTED (Docker) with the 12-skill version; not re-run after `environment-assessment` was added |
| Antigravity | start `agy` in the project; ask which subagents and skills it sees | in the validation, the headless session listed the `security-*` subagents and 12 skills | EXECUTED via a model question |
| Antigravity | `agy agents` | printed **nothing** in this session, both outside and inside an installed project | **NOT usable as proof** |

`claude agents` is *not* a subagent list: its help says "Manage background agents".

A repeatable version of these checks is in `tests/smoke/{claude,opencode,antigravity}.sh` (they use model quota; see [COMMAND-REFERENCE.md](COMMAND-REFERENCE.md)).

## 4. The five agents

Real names (use exactly these). Permissions below come from `agents/manifest.json` and the generated native files; "enforced by" tells you whether the tool or only the prompt holds the line.

| Agent | Role | Skills it loads | Can write? | Enforced by |
|---|---|---|---|---|
| `security-auditor` | read-only audit, evidence, severity | `environment-assessment`, `security-audit` | no | tool allow-list (Claude: Read/Grep/Glob; OpenCode: edit+bash deny; Antigravity: view_file, grep_search) — EXECUTED |
| `security-architect` | discovery, threat model, plan | `environment-assessment`, `security-audit`, `threat-modeling`, `framework-adapter-development` | no | same as auditor — EXECUTED |
| `security-implementer` | implement an **approved** plan, with tests | `auth-hardening`, `api-security`, `rate-limiting`, `request-observability`, `bot-detection`, `audit-trail`, `devsecops` | yes | Claude: write needs approval (default mode) — EXECUTED; OpenCode: `edit: ask`; Antigravity: **no confirmation if your global `permission_mode` is `always-proceed`** |
| `security-reviewer` | independent validation in a fresh context | `environment-assessment`, `security-validation` | no source edits | Claude: has `Bash` (to run tests) → read-only by instruction + approval prompt only (L1); OpenCode: edit deny, bash ask; Antigravity: `run_command` in sandbox policy |
| `security-orchestrator` | sequences the others; **stage 0 = environment and scope** | `environment-assessment`, `security-audit`, `security-validation` | no | delegates; Claude: `Agent` tool (delegation **not verified**); OpenCode: `task`; Antigravity: `invoke_subagent` (EXECUTED) |

`incident-response` is not assigned to any agent. Ask for it from the main session (name the skill in your prompt).

### 4.1 Invoking an agent — differs per tool
Do **not** assume the same syntax in all three tools.

- **Claude Code**: start a session *as* the agent: `claude --agent security-auditor` (EXECUTED with `-p`). Inside any session you can also ask in natural language "use the security-reviewer subagent to …" (DOCUMENTED behaviour; not run here).
- **OpenCode**: only the **primary** agent (`security-orchestrator`) can be selected with `opencode run --agent security-orchestrator "…"` (EXECUTED, headless, Docker); selecting it in the interactive TUI was **not verified**. `--agent <subagent>` silently falls back to the default `build` agent, which can write — this invalidated a first test. To reach the others, ask the orchestrator to delegate, or mention the subagent in the prompt (`@security-auditor`, DOCUMENTED).
- **Antigravity**: `agy --agent security-orchestrator -p "…"` (EXECUTED); the orchestrator is `mainAgent: true`, the other four are subagents reached through delegation (`invoke_subagent`, EXECUTED).

If delegation is unavailable, the orchestrator's own procedure says to run the stages sequentially and state that fallback in the report.

## 5. Skills: when to use which

Skills are loaded by the agents above, or named explicitly in your prompt ("apply the `rate-limiting` skill").

| Goal | Skill | Output |
|---|---|---|
| Which environment is this, what may I test, what mode applies | `environment-assessment` | environment profile, scope, mode, assessment matrix |
| "Is this secure?" / pre-release audit | `security-audit` | audit report with coverage matrix, findings `file:line` |
| Model a feature before building | `threat-modeling` | STRIDE table, scored threats, mitigations → skill → signal → test |
| Login, OTP, tokens, sessions, policies, tenant isolation | `auth-hardening` | changes + tests + residual risks |
| Endpoint hardening: validation, CORS, uploads, SSRF, webhooks | `api-security` | endpoint matrix before/after + negative tests |
| Brute force / resource abuse | `rate-limiting` | route class × key × limit × store-failure behaviour |
| Structured, redacted request events | `request-observability` | middleware order, fields, redaction, sample event |
| Detect automated abuse (observe-first) | `bot-detection` | rules `id@version`, fixtures TP/FP, promotion criteria |
| Tamper-evident audit of sensitive actions | `audit-trail` | audited actions, storage, redaction, tests |
| CI/CD, dependency/secret scanning, containers | `devsecops` | jobs, permissions, pins, failing-then-passing evidence |
| Active incident / runbooks | `incident-response` | UTC timeline, actions with approver and expiry |
| Gate before merge/release | `security-validation` | Approve / Approve with conditions / Reject + Implemented / Tested / Unverified |
| New framework adapter | `framework-adapter-development` | mapping table, cross-framework tests |

Every skill has the same 11 sections (purpose … required report format). The required report format is what you should expect back; reject an answer that does not follow it.

## 6. The standard workflow

```
audit (read-only) ─▶ threat model ─▶ PLAN ─▶ YOU APPROVE ─▶ implement + tests ─▶ independent review ─▶ release gate
 security-auditor     security-architect                      security-implementer   security-reviewer      security-validation
```

1. **Before coding** — threat model the feature (`security-architect`).
2. **While developing** — implementer with the relevant skill, one control at a time.
3. **Before each merge** — audit + regression tests.
4. **After fixes** — reviewer in a *new* session, never the implementer's.
5. **Before deploy** — dependencies, secrets, config, logs, rollback (`devsecops`, `security-validation`).

Copy-ready prompts for each step: [EXAMPLES.md](EXAMPLES.md).

## 6b. Environment-aware assessments (code audit, staging, production)
A code audit does not validate a deployed system. Before auditing, the agents identify the environment and the authorized scope, then pick a mode (skill `environment-assessment`, rules enforced by the deterministic `scripts/assessment-gate.py`, which does not depend on any model).

| Mode | When | Covers | Never |
|---|---|---|---|
| `code-only` | environment unknown or ambiguous (default) | source and configuration, non-destructive | active tests; ask first |
| `local` | confirmed local | static audit: OWASP Top 10 / API Top 10 / relevant ASVS, authn/authz/RBAC, injection, SSRF, IDOR/BOLA, secrets, dependencies, containers, CI/CD, security tests; lists what cannot be verified without a deployment | claiming network, TLS, IAM or runtime controls were verified |
| `staging` | confirmed staging + explicit scoped authorization | code **and** the authorized surface: TLS, headers, CORS, cookies, DNS, DAST/API tests, controlled fuzzing, authz and session tests, rate limiting, logging | targets outside the scope, real users, no limits/window/rollback |
| `production` | confirmed production + explicit authorization | operational posture, read-only: exposure, effective access control, headers/TLS, cloud/network, containers and supply chain, secrets management, logging/alerting/IR/backups | brute force, load, exploitation, account changes, data exfiltration, live enforcement |

How the environment is decided: only **verifiable evidence** counts (deployment manifest, CI deploy job, infrastructure definition, environment configuration, runtime metadata). A hostname or URL containing "staging", "test" or "dev" is **not** evidence; an owner's declaration alone is not enough; conflicting evidence ⇒ `unknown`. Reachability is never authorization.

Steps for a project:
```bash
cp adapters/project/assessment-scope.yaml.template <app>/.security-engineering/assessment-scope.yaml   # from the toolkit repo; fill in evidence and, if you authorize active tests, the authorization block
python3 <app>/.security-engineering/shared/scripts/assessment-gate.py classify <app>/.security-engineering/assessment-scope.yaml
python3 <app>/.security-engineering/shared/scripts/assessment-gate.py check <scope> --activity active_read_only --target https://app.example.org/ --now 2026-01-02T09:00:00Z   # exit 0 allow, 3 needs_confirmation, 1 deny
python3 <app>/.security-engineering/shared/scripts/assessment-gate.py validate-report report.json
```
(The gate needs python3 + PyYAML; the template is not copied automatically by the installer.) The agents have **no network tool**: even when the gate says `allow`, an active test is run by a human or an approved tool, not by the read-only agents. Every assessment ends with a matrix (control, environment, method, evidence, result `PASS/FAIL/PARTIAL/NOT_TESTED/NOT_APPLICABLE`, severity, confidence, remediation, retest) and a summary that separates verified secure controls, confirmed vulnerabilities, partially verified controls, unverified controls and limits, and tests intentionally not performed. **A PASS needs evidence; missing evidence is `NOT_TESTED`. No report may call the application "secure"** — the validator rejects it.

Hard rules in every environment: `exploitation` and `enforcement_action` (account lock, session revocation, IP/firewall block) are never initiated by an agent; request caps are 200 / 50 / 5 requests per second (local / staging / production); in production, load, fuzzing, state-changing tests and sensitive-data collection also need a specific, attributed, unexpired exception with a safety plan. Runtime enforcement stays observe-only. Quality criteria and the improvement cycle: `core/assessment-quality-gate.md`.

Cross-tool consistency (real sessions, 4 fictional scenarios, one run each): Claude Code (haiku), Antigravity and OpenCode (free model, Docker) all returned the gate's environment and decision — see `docs/validation-v0.1.0.md` §10 for limits.

## 7. Read-only versus write-enabled work

| Mode | Agents | Use for | Rule |
|---|---|---|---|
| Read-only | auditor, architect (and reviewer for source) | audit, threat model, plan, review | never ask them to "fix"; they cannot, and a prompt asking otherwise is a red flag |
| Write-enabled | implementer only | applying an approved plan | work on a branch; approve each write; run the tests it names |

Rules that hold in every tool: no production access; no secrets in prompts (reports give path + type only); detection and response rules start in `observe`; blocking, account lock and session revocation need your explicit approval; no LLM output is an enforcement authority.

### Approval requirements and tool-specific limits
- **Claude Code** — the implementer's `Edit`/`Write` need approval in default permission mode (EXECUTED: an unapproved write was denied). Do not pre-approve `Bash(*)` for the reviewer: that removes its only technical barrier (**L1**).
- **OpenCode** — `edit` and non-trivial `bash` are `ask`. Headless `opencode run` cannot answer a prompt, so the write was rejected (**L2**); interactive confirmation was **not exercised**.
- **Antigravity** — no per-agent confirmation. With `permission_mode: always-proceed` (the global setting found on the validation machine) the implementer writes without asking (**L4**). Run the implementer in a throw-away branch, or switch the mode to ask before using it.
- Interactive confirmation prompts were not exercised in any tool.

## 8. Expected outputs and evidence

An acceptable answer:
- follows the skill's section 11 report format;
- cites `file:line` for every finding, with severity and a safe verification method;
- lists commands run and their results (exact command, exit code, counts);
- ends with **Implemented / Tested / Unverified**; an item is "Tested" only if the agent ran a test and shows the output;
- never prints secret values.

Reject, and ask again, if an answer claims a test passed without showing the command, or says "secure" without a verification.

## 9. End-to-end examples (no production access)

### 9.1 Laravel (project mode)
```bash
scripts/install.sh --mode project --project-dir ~/dev/my-laravel-app --vendor-skills
$EDITOR ~/dev/my-laravel-app/.security-engineering/config.yaml   # framework: laravel, verify_commands.tests: "php artisan test"
cd ~/dev/my-laravel-app && git checkout -b security/audit-1
claude --agent security-auditor            # then paste "Read-only security audit" from EXAMPLES.md
```
Then `claude --agent security-architect` for the plan, approve it, `claude --agent security-implementer` for one finding at a time, and a fresh `claude --agent security-reviewer` to validate. The PHP/Composer dependencies of *your* app should run in Docker if the host lacks extensions; the agents only read code unless they are the implementer.

### 9.2 NestJS (project mode)
Same steps with `framework: nestjs` and `verify_commands.tests: "npm test"`; the skills name `ValidationPipe`, Guards, `@nestjs/throttler`, interceptors and exception filters.

### 9.3 Wiring the observe-mode runtime (optional, separate from the agents)
`adapters-runtime/{laravel,nestjs}` is a reference runtime that emits redacted events and evaluates the 7 shipped detection rules in `observe`. It is **not** installed by the agent installer; follow "Runtime wiring" in [project-integration.md](project-integration.md). It never blocks in `observe`. It has no Redis or worker: state is per-process memory.

## 10. First-use walkthrough (nothing touches production)

1. `cd ~/Apps/security-engineering && git status --short && cat VERSION` — clean tree, version `0.1.0`.
2. `tests/run_all.sh --no-docker` — confirms the toolkit itself is healthy (needs python3 + PyYAML). Docker integration tests run when you omit `--no-docker`.
3. Create a throw-away sample: `cp -r tests/fixtures/smoke-project /tmp/se-sample && cd /tmp/se-sample && git init && git add -A && git commit -m sample`.
4. `~/Apps/security-engineering/scripts/install.sh --mode project --project-dir /tmp/se-sample --vendor-skills` (dry-run first).
5. Open your tool in `/tmp/se-sample` and check discovery (section 3).
6. Run the *Read-only security audit* prompt with `security-auditor`. Confirm `git status` shows no change (the auditor cannot write).
7. Only then repeat on a real project, on a branch, still without production credentials.

Clean up: `scripts/uninstall.sh --mode project --project-dir /tmp/se-sample`.

## 11. Troubleshooting

| Symptom | Likely cause / action |
|---|---|
| install exits **3** | a destination file differs from ours (conflict). Review it; `--force` backs it up as `*.bak.<UTC>` |
| install exits **4** | version downgrade or project pin mismatch; review, then `--allow-version-change` |
| `validate-installation.sh` reports missing/modified files | re-run install (idempotent); modified managed files are kept and reported |
| Agents not visible in a tool | check the install target for that tool and mode (project vs global); restart the tool; some tools read agents only at start-up |
| Duplicate skill warnings | OpenCode also reads `.claude/skills`; when Claude is installed the installer skips OpenCode's own copy on purpose |
| OpenCode runs the wrong agent | `--agent <subagent>` falls back to `build`; select `security-orchestrator` |
| Antigravity subagent hangs | a misspelled tool name; names are checked against `tests/fixtures/antigravity-tool-catalog.json` |
| Antigravity crash-loop after mass skill install | do not bulk-install into `~/.agents/skills`; this toolkit installs 13 skills in `~/.gemini/config/skills` |
| Implementer wrote without asking (Antigravity) | expected under `always-proceed` (L4) |
| Model call fails in smoke tests | the result is reported `NOT VERIFIED`, not PASS |
| PyYAML missing for tests | `pip install -r requirements-dev.txt` (in a virtualenv or container) |

## 12. Update, roll back, uninstall
```bash
scripts/uninstall.sh --mode project --project-dir ~/dev/my-app --dry-run
scripts/uninstall.sh --mode project --project-dir ~/dev/my-app
scripts/uninstall.sh --mode global [--restore-backups]
# Windows: scripts/uninstall.ps1 -Mode global
```
Uninstall removes only unmodified files the installer created, keeps files you edited or that pre-existed, removes only the managed block from `CLAUDE.md`/`AGENTS.md`, and is safe to run twice (TESTED, `tests/installer`). Update: check out the new tag, re-run the installer (add `--allow-version-change` for a pin change), review the diff, validate.

## 13. Known limitations (read before relying on this)
- Windows native and macOS: not executed.
- Interactive confirmation prompts: not exercised in any tool.
- Claude reviewer has `Bash`; Antigravity cannot enforce confirm-before-write.
- The runtime keeps state in process memory (restart loses blocks); `account_lock`, `session_revocation` and `challenge` are never executed — always routed to manual review.
- No pilot on a real application has been run yet.
- The agents have no network or dynamic-scanning tool: they read code and run only the tests/commands you configure.
- OWASP coverage is partly guidance: see [OWASP-COVERAGE.md](OWASP-COVERAGE.md). It is not a compliance claim.
