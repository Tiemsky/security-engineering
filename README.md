# security-engineering

One canonical security methodology (skills + agent specs + contracts + policies) deployed natively into **Claude Code**, **Google Antigravity** and **OpenCode**, with reference runtimes for **Laravel** and **NestJS**.

> Installing skills does **not** secure an application. Skills drive an agent to *implement and verify* protections in your code; the runtime (`adapters-runtime/`) is what executes in production.

## Getting started
New here? Read in this order:
1. [`docs/USER-GUIDE.md`](docs/USER-GUIDE.md) — install, discover and invoke the 5 agents in Claude Code / OpenCode / Antigravity, workflows, limits, troubleshooting, a first walkthrough that needs no production access.
2. [`docs/EXAMPLES.md`](docs/EXAMPLES.md) — copy-ready prompts (audit, threat model, auth review, BOLA/IDOR, rate limiting, dependency/secret scan, fix with regression tests, independent review, pre-release validation).
3. [`docs/COMMAND-REFERENCE.md`](docs/COMMAND-REFERENCE.md) — every command, with whether it was actually executed. The three tools do **not** share one invocation syntax.
4. **Before any audit or active test**: [`skills/environment-assessment`](skills/environment-assessment/SKILL.md) and `scripts/assessment-gate.py` — the environment is established from verifiable evidence and active tests need an explicit scoped authorization (see USER-GUIDE §6b).
5. [`docs/PILOT-PROTOCOL.md`](docs/PILOT-PROTOCOL.md) — repeatable read-only audit of any application: audit copy without secrets, scope, run, report validation, independent verification.
6. [`docs/OWASP-COVERAGE.md`](docs/OWASP-COVERAGE.md) — traceability to OWASP Top 10:2025, API Top 10:2023, ASVS 5.0.0 and WSTG; distinguishes guidance from implemented and tested controls. It is not a compliance claim.

## Layout
| Path | Role |
|---|---|
| `skills/<name>/SKILL.md` | Canonical skills (13). Agent Skills format; `name` == directory. Single source of truth |
| `agents/` | Conceptual agent specs + `manifest.json` (per-tool capabilities). `scripts/build-adapters.py` generates the native files |
| `adapters/<tool>/` | Generated native agents, Antigravity rule, instruction templates, `opencode.json.template` |
| `core/` | Principles, execution policy, orchestrator, completion criteria |
| `contracts/` | Versioned JSON Schemas (access, security, audit, decision, outcome, rule, health, deployment) + compatibility rules |
| `policies/` | Deterministic YAML: defaults (observe-only), detection rules, response actions, redaction |
| `adapters-runtime/{laravel,nestjs,generic}` | Reference runtime wired into the real request path |
| `scripts/` | `install.sh`, `install.ps1`, `uninstall.sh`, `validate-installation.sh`, `build-adapters.py`, `compile-policies.py`, `audit-copy.sh`, `extract-report-json.py`, `assessment-gate.py` |
| `tests/` | Unit, installer, contract, policy, agent-boundary and Docker-based runtime integration tests |
| `docs/` | User guide, command reference, examples, OWASP coverage matrix, ADR, compatibility, installation, project integration, validation report |

## Quick start
```bash
# 1) global (current user) — dry-run first
scripts/install.sh --mode global --dry-run
scripts/install.sh --mode global                 # tools auto-detected; or --tools claude,opencode,antigravity
scripts/validate-installation.sh --mode global   # static verification only

# 2) per application: minimal pinned integration package
scripts/install.sh --mode project --project-dir ~/dev/my-app
scripts/validate-installation.sh --mode project --project-dir ~/dev/my-app
```
Windows: `scripts/install.ps1 -Mode global -DryRun`. Details: `docs/installation.md`, `docs/project-integration.md`.

## Workflow
Scope (`environment-assessment`: local / staging / production / unknown, authorized scope) → Orchestrator → Architect (audit + threat model + plan) → **you approve** → Implementer (tests included) → Reviewer (fresh context) → report *Implemented / Tested / Unverified*. Detection and response run in **observe** until you promote a rule.

## Tests
```bash
tests/run_all.sh              # needs python3 + PyYAML (+ Docker for the real Laravel/NestJS integration run)
SE_SKIP_DOCKER=1 tests/run_all.sh
```
See `docs/status.md` (implemented / tested / unverified) and `docs/validation-v0.1.0.md` (validation report and release decision).
