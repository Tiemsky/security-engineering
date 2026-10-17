# Active testing — the gate-driven pentest runner

`scripts/pentest-runner.py` runs **active** security checks (requests are sent to a target) against an application you own or are explicitly authorized to test. It is the executor the read-only agents are not: the agents read code, this runner sends requests. It is built so that it cannot act outside what the deterministic gate permits.

Labels: **TESTED** (automated test in `tests/pilot/test_pentest_runner.py`) · **EXECUTED** · **NOT-VERIFIED**.

## Safety model (why this is not a free-fire tool)
- **Gate-first.** Before every module the runner calls `scripts/assessment-gate.py check` for that module's activity class and runs the module **only** when the decision is `allow`. `needs_confirmation` and `deny` skip the module and send nothing. This is TESTED, including a mutation check: bypassing the gate makes the "nothing is sent on deny" test fail. — TESTED
- **Non-destructive by construction.** Every shipped module sends only `GET` requests and never follows them with a state change. There is no `exploitation` or `enforcement_action` module, and the gate denies both classes anyway (`G01-never-by-agent`). Confirming a SQL-injection or IDOR *exposure* is detection; dumping data, dropping tables or taking a shell is exploitation and stays a human decision through a controlled process.
- **Paced.** Requests are spaced under `min(authorization.limits.max_requests_per_second, cap)` where the cap is 200 (local) / 50 (staging) / 5 (production). — TESTED on loopback.
- **Loopback-first.** A confirmed-local, loopback target is allowed without authorization (gate `G05`); any non-local target needs explicit, attributed authorization, an in-window test window and recorded limits. Point the runner at a throw-away instance before anything you care about.
- **Separate from the agents.** The runner is not an agent and gets no agent permissions; installing it never widens any agent (`tests/agents` unchanged).

## Modules shipped (all `active_read_only`)
| Module | Checks | Needs | Matrix topic |
|---|---|---|---|
| `http-headers` | HSTS, CSP, X-Content-Type-Options, X-Frame-Options, Referrer-Policy | stdlib | `http_headers_cors_cookies` |
| `cookie-flags` | Set-Cookie Secure / HttpOnly / SameSite | stdlib | `http_headers_cors_cookies` |
| `cors` | reflected-origin and credentialed CORS | stdlib | `http_headers_cors_cookies` |
| `tls` | negotiated TLS version, certificate validity and expiry | stdlib | `tls_certificates` |
| `tls-scan` | deep TLS scan (protocols, ciphers, cert) via `testssl.sh` | `testssl.sh` | `tls_certificates` |
| `http-scan` | template-based HTTP scan via `nuclei` (detection templates, no DAST) | `nuclei` | `dast_api_testing` |

A module whose required binary is absent is skipped with a clear message (`shutil.which`), so a checkout with no external tool still runs the stdlib modules. — TESTED (with a fake `testssl.sh`, so no real scan runs in CI). External tools that manage their own connection cadence (testssl among them) are not paced request-by-request by the runner; the run log marks this as `rate_enforced_by_runner: false`, and the gate's authorization, window and scope still govern whether the tool runs at all.

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

A module declares its required binaries in `needs`; the runner skips it with a clear message when a binary is absent, and (for tools that take one) passes the gate's rate cap to the tool's own rate flag. `tls-scan` (via `testssl.sh`) is the first external-tool module and the pattern for the rest. Exploitation modules are intentionally out of scope.

`tls-scan` needs [`testssl.sh`](https://testssl.sh/) on `PATH`. It runs `testssl.sh --quiet --color 0 --jsonfile-pretty <tmp> <target>` (no shell, bounded timeout, target passed as a positional argument), then maps each JSON entry's severity (`CRITICAL/HIGH/MEDIUM/LOW` → FAIL; `WARN` → NOT_TESTED; `OK/INFO` → ignored). It reads only — it enumerates protocols, ciphers and the certificate and changes nothing — so it is `active_read_only`.

`http-scan` needs [`nuclei`](https://github.com/projectdiscovery/nuclei) on `PATH`. It runs `nuclei -target <target> -jsonl -o <tmp> -silent -duc -ni -rl <cap> -timeout 10 -no-color` and maps each result's `info.severity` (`CRITICAL/HIGH/MEDIUM/LOW` → FAIL; `info` → ignored as a detection, not a weakness). Three safety choices make it `active_read_only` rather than fuzzing, and all three are TESTED by asserting the argv the module passes:
- **no `-dast`** — detection templates only; nuclei's fuzzing/DAST templates are not enabled here (injection fuzzing will be a separate `active_fuzzing` module);
- **`-ni`** — interactsh out-of-band callbacks disabled, so the scan contacts no third-party server;
- **`-rl <cap>`** — nuclei's own rate limit set to the gate's cap (`min(authorization.limits.max_requests_per_second, env cap)`).

nuclei manages its own templates and needs internet access on first use to fetch them; that fetch is nuclei's, not the runner's. Point `http-scan` at your own instance first.
