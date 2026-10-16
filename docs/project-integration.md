# Project integration (minimal, version-pinned)
```bash
scripts/install.sh --mode project --project-dir ~/dev/my-app            # creates the package below
scripts/install.sh --mode project --project-dir ~/dev/my-app --vendor-skills   # team-shared pinned copy of skills/agents in the repo
```
Creates (commit these): `.security-engineering/config.yaml` (pinned `security_engineering_version`, framework, mode, trusted proxies, approved exceptions, verify commands), `PROJECT_RULES.md`, managed blocks in `CLAUDE.md`/`AGENTS.md`, merged `opencode.json` `instructions`, native agents in `.claude/agents`, `.opencode/agents`, `.agents/{agents,rules}`. It does **not** copy the whole repository; skills are vendored only with `--vendor-skills`.

## Pin / update / validate / roll back
1. Pin = `security_engineering_version` in `config.yaml`.
2. Update: checkout the new central tag, run `install.sh --mode project … --allow-version-change`, review the diff in git, run `validate-installation.sh --mode project …`.
3. Roll back: `git revert` the integration commit (or `uninstall.sh --mode project`).
4. Team rule: a mismatched pin is refused by the installer, so nobody works on an unnoticed different version.

## Runtime wiring (what actually protects production)
1. `python3 scripts/compile-policies.py <app>/config/security-policies` (YAML → JSON; runtimes need no YAML parser).
2. **Laravel**: add `adapters-runtime/laravel/src` (PSR-4 `SecurityEngineering\`), register `SecurityEngineeringServiceProvider`, prepend `HttpAccessMiddleware`, set `config/security-engineering.php` (`policy_dir`, `trusted_proxies`). Feed `DecisionEngine::observe()` from your login/OTP/webhook code (see `examples/AuthProbeController.php`).
3. **NestJS**: import `SecurityModule.register({...})`, apply `SecurityMiddleware` globally, provide `AccessInterceptor` (APP_INTERCEPTOR) and `AccessExceptionFilter` (APP_FILTER); inject `SE_ENGINE` where auth events occur (see `examples/auth-probe.controller.ts`). Never set `testPeerHeader` outside tests.
4. Keep `mode: observe`; promote a single rule at a time after reviewing `would_act` decisions and false positives.
5. Store secrets in your secret manager — never in `config.yaml`, skills or agent files.
