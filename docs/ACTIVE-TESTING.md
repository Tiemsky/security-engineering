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
| `content-discovery` | path/content discovery via `ffuf` (needs `--wordlist`; flags exposed sensitive/admin paths) | `ffuf` | `dns_exposed_services` |
| `port-scan` | exposed-services scan via `nmap` (flags data-store / insecure-remote ports) | `nmap` | `dns_exposed_services` |
| `injection-fuzz` | SQL-injection **detection** via `sqlmap` (no dump / shell / enumeration) | `sqlmap` | `injection` |
| `idor-bola` | object-level authorization (IDOR/BOLA) with a dedicated test account | stdlib | `idor_bola` |
| `priv-esc` | privilege escalation / function-level authz (BFLA) with a low-privilege test account | stdlib | `authorization_rbac` |

`injection-fuzz` is the first `active_fuzzing` module: the gate requires an explicit, attributed authorization with a window and limits for staging, a valid `production_exception` for production, and allows it on a confirmed-local loopback target (`G05`). Everything above it in the table is `active_read_only`.

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

`idor-bola` is the first `active_authenticated` module. It reads only (GET) with a **dedicated test account** and checks object-level authorization: for each probe in `--probes` (template: `adapters/project/idor-probes.yaml.template`) it confirms the account can read its own object, then that each *foreign* object id is denied (401/403/404) — a foreign `2xx` is a BOLA/IDOR FAIL — and that the endpoint is not readable with no credential at all (broken authentication, critical). The credential comes from `$SE_AUTH_HEADER` (preferred) or `--auth-header`, never the committed scope, and is never written to the run log or a finding (TESTED). Because it is `active_authenticated`, the gate requires the scope to record `test_accounts` on staging/production (rule `G12`): without them the module is held at `needs_confirmation` and no request is sent (TESTED). Real user accounts are never used.

`priv-esc` is the vertical counterpart of `idor-bola`, also `active_authenticated` and GET-only. It reads `privileged_paths` from `--probes` and checks that the **low-privilege** test account is denied each privileged endpoint (401/403/404) and that none is readable with no credential; a `2xx` is a privilege-escalation / broken-function-level-authorization FAIL (high), and an unauthenticated `2xx` is critical. Point `$SE_AUTH_HEADER` at the low-privilege account (an admin token would make every path look vulnerable). Same credential hygiene and `G12` test-account requirement as `idor-bola`. — TESTED.

`port-scan` needs [`nmap`](https://nmap.org/) on `PATH`. It runs `nmap -sT -Pn --top-ports 100 -sV --version-light --max-rate <cap> -T3 -oX <tmp> <host>` and parses the XML for open ports. It is deliberately non-intrusive and `active_read_only`: a TCP connect scan (`-sT`, no root), light version detection, and **no NSE scripts, no `-A`, no `-O`** (all asserted by a test on the argv). `--max-rate` is pinned to the gate's cap, so a production scan runs at 5 packets/second. It reports an exposed data-store or insecure-remote port (mysql, postgres, redis, mongodb, elasticsearch, memcached, mssql, docker API, rdp, vnc, telnet) as **high**, and lists the other open ports as one `info` surface finding. — TESTED with a fake `nmap`.

`content-discovery` needs [`ffuf`](https://github.com/ffuf/ffuf) on `PATH` and a wordlist you pass with `--wordlist PATH` (no wordlist ⇒ `NOT_TESTED`, the tool is not run). It runs `ffuf -u <target>/FUZZ -w <wordlist> -of json -o <tmp> -rate <cap> -t 10 -timeout 10 -noninteractive -s` (the `FUZZ` keyword is appended to the target if absent), reads only, and because the request volume is high its `-rate` is pinned to the gate's cap. It reports an exposed `.git`/`.env`/backup/key path as **high**, an admin/debug/console path as **medium**, and lists every other discovered path as one `info` "attack surface" finding (sample capped at 30). It is `active_read_only`. — TESTED with a fake `ffuf`.

`http-scan` needs [`nuclei`](https://github.com/projectdiscovery/nuclei) on `PATH`. It runs `nuclei -target <target> -jsonl -o <tmp> -silent -duc -ni -rl <cap> -timeout 10 -no-color` and maps each result's `info.severity` (`CRITICAL/HIGH/MEDIUM/LOW` → FAIL; `info` → ignored as a detection, not a weakness). Three safety choices make it `active_read_only` rather than fuzzing, and all three are TESTED by asserting the argv the module passes:
- **no `-dast`** — detection templates only; nuclei's fuzzing/DAST templates are not enabled here (injection fuzzing will be a separate `active_fuzzing` module);
- **`-ni`** — interactsh out-of-band callbacks disabled, so the scan contacts no third-party server;
- **`-rl <cap>`** — nuclei's own rate limit set to the gate's cap (`min(authorization.limits.max_requests_per_second, env cap)`).

nuclei manages its own templates and needs internet access on first use to fetch them; that fetch is nuclei's, not the runner's. Point `http-scan` at your own instance first.

`injection-fuzz` needs [`sqlmap`](https://sqlmap.org/) on `PATH`. It runs `sqlmap -u <target> --batch --risk=1 --level=2 --technique=BEUST --threads=1 --delay <1/cap> --timeout=15 --retries=1 --flush-session --output-dir <tmp>` and parses stdout to report whether a parameter is injectable. sqlmap's detection is itself a **differential proof** — it sends payloads and verifies the response changes (boolean `1=1` vs `1=2`, a real error, an actual `SLEEP` delay), so a reported injection point is confirmed injectable, not a pattern-match guess.

**It is detection (+ an optional benign confirmation), not exploitation.** It never builds — and refuses to run if its argv ever contained — any of `--dump`, `--os-shell`, `--os-cmd`, `--sql-shell`, `--file-read/-write`, `--dbs`, `--tables`, `--columns`, `--passwords`, `--users` and the other exfiltration/RCE/enumeration flags (`SQLMAP_FORBIDDEN`); this refusal is TESTED. The executor gives you no way to pass extra sqlmap flags. The target needs a testable parameter (e.g. `http://host/item?id=1`); the rate cap becomes sqlmap's `--delay` between requests.

### `--confirm`: benign proof that it is a real vulnerability
A detected injection is confirmed injectable; `run --confirm` adds a second step that proves data can actually be *read* through it, to settle any false-positive doubt — by retrieving **only** a non-sensitive scalar: `--banner`, `--current-user`, `--current-db`. No user data, no table, no credential, no dump, no shell. This step is a distinct `sensitive_data_collection` activity, **re-checked against the gate on its own**: on a confirmed-local loopback target it is denied (that class is not in the loopback allow-set), so `--confirm` needs explicit authorization even locally; in production it needs a `production_exception`. When the gate denies it, the finding stays a detection FAIL with a note that the benign proof was not run. All of this is TESTED (gate-denied fallback; authorized retrieval; destructive flags never passed).

Weaponised exploitation — dumping the database, enumerating credentials, `--os-shell` — is **not** automated by this executor: `exploitation` is `ALWAYS_DENIED` by the gate (`G01`). Demonstrating full impact for a proof-of-concept is a step you run by hand, with sqlmap directly, against a system you own and are authorized to exploit.
