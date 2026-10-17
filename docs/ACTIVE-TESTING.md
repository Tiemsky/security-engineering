# Active testing — the gate-driven pentest runner

`scripts/pentest-runner.py` runs **active** security checks (requests are sent to a target) against an application you own or are explicitly authorized to test. It is the executor the read-only agents are not: the agents read code, this runner sends requests. It is built so that it cannot act outside what the deterministic gate permits.

Labels: **TESTED** (automated test in `tests/pilot/test_pentest_runner.py`) · **EXECUTED** · **NOT-VERIFIED**.

## Safety model (why this is not a free-fire tool)
- **Gate-first.** Before every module the runner calls `scripts/assessment-gate.py check` for that module's activity class and runs the module **only** when the decision is `allow`. `needs_confirmation` and `deny` skip the module and send nothing. This is TESTED, including a mutation check: bypassing the gate makes the "nothing is sent on deny" test fail. — TESTED
- **Non-destructive by construction.** Every shipped module sends only `GET` requests and never follows them with a state change. There is no `exploitation` or `enforcement_action` module, and the gate denies both classes anyway (`G01-never-by-agent`). Confirming a SQL-injection or IDOR *exposure* is detection; dumping data, dropping tables or taking a shell is exploitation and stays a human decision through a controlled process.
- **Paced.** Requests are spaced under `min(authorization.limits.max_requests_per_second, cap)` where the cap is 200 (local) / 50 (staging) / 5 (production). — TESTED on loopback.
- **Loopback-first.** A confirmed-local, loopback target is allowed without authorization (gate `G05`); any non-local target needs explicit, attributed authorization, an in-window test window and recorded limits. Point the runner at a throw-away instance before anything you care about.
- **Separate from the agents.** The runner is not an agent and gets no agent permissions; installing it never widens any agent (`tests/agents` unchanged).

## Modules shipped (all `active_read_only`, stdlib only)
| Module | Checks | Matrix topic |
|---|---|---|
| `http-headers` | HSTS, CSP, X-Content-Type-Options, X-Frame-Options, Referrer-Policy | `http_headers_cors_cookies` |
| `cookie-flags` | Set-Cookie Secure / HttpOnly / SameSite | `http_headers_cors_cookies` |
| `cors` | reflected-origin and credentialed CORS | `http_headers_cors_cookies` |
| `tls` | negotiated TLS version, certificate validity and expiry | `tls_certificates` |

## Use
```bash
scripts/pentest-runner.py list                                   # modules, activity class, required binaries
scripts/pentest-runner.py plan  SCOPE.yaml --target URL          # gate decision per module; sends NOTHING
scripts/pentest-runner.py run   SCOPE.yaml --target URL --out DIR # runs only the modules the gate allows
```
`SCOPE.yaml` is the same file the gate uses (`adapters/project/assessment-scope.yaml.template`). For a non-local target, fill the `authorization` block (approver, targets, allowed_activities, window, limits) first, then `plan`, then `run`. The run log (`pentest-run.jsonl`) records, per module, the gate decision and the rule ids behind it, so a reviewer can see why each module ran or was skipped.

First time, against your own instance:
```bash
scripts/pentest-runner.py run adapters/project/assessment-scope.yaml.template --target http://127.0.0.1:8000/ --out /tmp/run
```
with a scope whose `declared_environment: local` and one `env_config` evidence item — the gate then returns `allow` via `G05` for a loopback target.

## Findings are leads
A FAIL is a lead to verify by hand, not proof; a PASS means only that this one check passed against this one response. Feed confirmed items into the assessment matrix (`contracts/assessment-report.schema.json`) and validate it with `scripts/assessment-gate.py validate-report`.

## Extending with external tools (design, NOT-VERIFIED)
More intrusive tools (TLS scanners, template/vuln scanners, content discovery, API/injection fuzzers) plug in as new entries in the `MODULES` registry, each declaring its **activity class** so the gate governs it:
- a scanner that only reads ⇒ `active_read_only`;
- a fuzzer / injection probe ⇒ `active_fuzzing` (the gate requires authorization + window + limits, and in production a specific, unexpired `production_exception`);
- an authenticated crawl using a **dedicated test account** ⇒ `active_authenticated` (gate `G12` requires the account to be recorded).

A module declares its required binaries in `needs`; the runner skips it with a clear message when a binary is absent, and always passes the gate's rate cap to the tool's own rate flag. No external-tool module ships yet — adding one is the next increment, after you confirm which tools to wire in. Exploitation modules are intentionally out of scope.
