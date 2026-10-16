# security-engineering

One canonical security methodology (skills + agent specs + contracts + policies) deployed natively into **Claude Code**, **Google Antigravity** and **OpenCode**, with reference runtimes for **Laravel** and **NestJS**.

> Installing skills does **not** secure an application. Skills drive an agent to *implement and verify* protections in your code; the runtime (`adapters-runtime/`) is what executes in production.

## Layout
| Path | Role |
|---|---|
| `skills/<name>/SKILL.md` | Canonical skills (12). Agent Skills format; `name` == directory. Single source of truth |
| `agents/` | Conceptual agent specs + `manifest.json` (per-tool capabilities). `scripts/build-adapters.py` generates the native files |
| `adapters/<tool>/` | Generated native agents, Antigravity rule, instruction templates, `opencode.json.template` |
| `core/` | Principles, execution policy, orchestrator, completion criteria |
| `contracts/` | Versioned JSON Schemas (access, security, audit, decision, outcome, rule, health, deployment) + compatibility rules |
| `policies/` | Deterministic YAML: defaults (observe-only), detection rules, response actions, redaction |
| `adapters-runtime/{laravel,nestjs,generic}` | Reference runtime wired into the real request path |
| `scripts/` | `install.sh`, `install.ps1`, `uninstall.sh`, `validate-installation.sh`, `build-adapters.py`, `compile-policies.py` |
| `tests/` | Unit, installer, contract, policy, agent-boundary and Docker-based runtime integration tests |
| `docs/` | ADR, compatibility matrix, installation, project integration |

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
Orchestrator → Architect (audit + threat model + plan) → **you approve** → Implementer (tests included) → Reviewer (fresh context) → report *Implemented / Tested / Unverified*. Detection and response run in **observe** until you promote a rule.

## Tests
```bash
tests/run_all.sh              # needs python3 + PyYAML (+ Docker for the real Laravel/NestJS integration run)
SE_SKIP_DOCKER=1 tests/run_all.sh
```
See `docs/status.md` for what is implemented, tested and unverified.
