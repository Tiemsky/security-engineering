# Copy-ready prompts

Each example gives: **agent** to start, **scope**, **allowed actions**, **prohibited actions**, **expected evidence**, **acceptance criteria**, then the prompt. Replace `<…>` placeholders. Agent names are the real ones; start them the way your tool requires ([COMMAND-REFERENCE.md §3](COMMAND-REFERENCE.md#3-native-agent-invocation)).

These are prompts, not commands: a model may still deviate. Check the acceptance criteria every time, and run the work on a **branch of a non-production checkout**. Never paste secrets, tokens, production URLs or real user data into a prompt. Each skill's required report format ([USER-GUIDE.md §5](USER-GUIDE.md#5-skills-when-to-use-which)) is what you should get back.

Examples 10–12 are **environment-aware**: use them when a URL, a deployment or active testing is involved. Every audit first establishes the environment from verifiable evidence (never from a hostname) and the authorized scope; see [USER-GUIDE.md §6b](USER-GUIDE.md#6b-environment-aware-assessments-code-audit-staging-production).

Common clauses (already included in each prompt): no production access, no secret values in output (path and type only), separate **Implemented / Tested / Unverified**, say "not executed" instead of inferring a pass.

---

## 1. Read-only security audit
- **Agent / skill:** `security-auditor` / `security-audit`
- **Scope:** the repository, or the module you name. Laravel or NestJS.
- **Allowed:** read files, grep, glob. (Nothing else is available to this agent.)
- **Prohibited:** editing or creating files, running the app, network calls, printing secret values.
- **Evidence:** coverage matrix (entry point × authn / authz / object-level / validation / rate-limit / audit); each finding with `file:line`, severity, impact, safe verification; list of unverified areas.
- **Acceptance:** every route/webhook/job/upload has a matrix row; every finding has file:line evidence; `git status` shows no change; no secret value in the report.

```text
Perform a read-only security audit of <repo path or module> using the security-audit skill.
Detect the framework and version first, and read .security-engineering/config.yaml if present.
Cover authentication, authorization (object-level and tenant), input validation and mass assignment, file uploads, SSRF, webhooks, CORS and headers, secrets, dependencies (report the lockfile state; only run composer audit / npm audit if I have allowed it), logging and error handling.
Do not modify any file, do not run state-changing commands, do not contact external systems, and never print secret values (report path and secret type only).
Output the security-audit report format: scope and not-covered, coverage matrix, findings (ID, severity, title, file:line, impact, fix skill, verification), unverified items, counts by severity.
For every High/Critical finding give a safe, reproducible check that a future test can assert.
```

## 2. Threat modeling
- **Agent / skill:** `security-architect` / `threat-modeling` (+ `security-audit` for discovery)
- **Scope:** one feature or flow, e.g. "tenant invitation + OTP login".
- **Allowed:** read code and docs, produce a text model and plan.
- **Prohibited:** code changes, assuming components that are not in the code (list them as assumptions), real data.
- **Evidence:** assets, actors, trust boundaries, data-flow table, STRIDE threats scored L×I, each threat ≥4 with mitigation → skill → signal (event type from `contracts/`) → test name; assumptions with owner.
- **Acceptance:** all flows crossing a trust boundary analysed; every threat ≥4 has the four mappings; accepted risks are marked "needs your sign-off", not self-approved.

```text
Create a threat model for <feature> using the threat-modeling skill. Read the relevant code first; list anything you cannot confirm as an assumption marked "needs confirmation".
Include assets, actors (anonymous, user, admin, service, tenant), trust boundaries, a data-flow table (source → destination | data | boundary | protocol), STRIDE per flow and store, and abuse cases (credential stuffing, OTP brute force, enumeration, scraping, webhook replay, tenant hopping).
Score likelihood × impact (1–3 each). For every threat scored 4 or more give: mitigation, the implementing skill, the observable signal, and a named test.
Then propose an ordered implementation plan (files expected to change, tests per control, rollout in observe mode, rollback, items needing my approval). Do not edit any file and do not approve the plan yourself.
```

## 3. Authentication and session review
- **Agent / skill:** `security-auditor` (review) then `security-architect` (plan); `auth-hardening` guides the checks.
- **Scope:** login, register, password reset, OTP/MFA, token issuance/refresh/revocation, session config, logout.
- **Allowed:** read-only.
- **Prohibited:** testing against real accounts, brute-forcing anything, printing tokens/OTPs/hashes.
- **Evidence:** per flow: hashing algorithm, uniform error messages, throttling on login/reset/OTP, session regeneration, logout invalidation, token lifetime/rotation/hashing, OTP rules (length, expiry, single use, attempt caps per identifier and IP).
- **Acceptance:** each flow has a pass/fail line per control with `file:line`; missing controls are mapped to `auth-hardening` / `rate-limiting`; unverified items listed.

```text
Review authentication and session handling in <repo/module> as read-only, applying the checks of the auth-hardening skill (section 5) without changing anything.
For login, registration, password reset, OTP/MFA, API/refresh tokens, sessions and logout, report for each control whether it is present, with file:line: password hashing (argon2id/bcrypt), constant-time comparison, uniform errors (no user enumeration), throttling per IP and per identifier, session ID regeneration on login and privilege change, server-side logout, token lifetime / rotation / reuse detection / hashed storage, OTP length, expiry (≤10 min), single use, attempt caps and resend cooldown.
Never print credentials, tokens, OTPs or hashes. Do not attempt logins. Rank findings by severity and name the skill that fixes each one. List what you could not verify.
```

## 4. API authorization and BOLA/IDOR testing
- **Agent / skill:** audit by `security-auditor`; tests by `security-implementer` after approval; check by `security-reviewer`. Skills `auth-hardening`, `security-validation`.
- **Scope:** the endpoints that take an object id (`/orders/{id}`, `/tenants/{t}/…`).
- **Allowed:** (auditor) read-only. (implementer) add negative tests and minimal authorization fixes **after your approval**, run the local test suite.
- **Prohibited:** testing a deployed environment, using real user ids, weakening an existing check to make a test pass.
- **Evidence:** table route → object lookup → ownership/tenant check → existing negative test; new tests named; their real output.
- **Acceptance:** for every object-id route there is a test where user A (and tenant A) requesting B's object gets 403/404; tests fail on the unfixed code and pass after; authorization matrix attached.

Step 1 (read-only):
```text
List every route that accepts an object identifier (path, query or body) in <repo/module>. For each give: the lookup call (file:line), whether ownership or tenant is enforced (policy/gate/guard/scope), and whether a negative cross-user and cross-tenant test exists. Flag any find()/findOrFail()/repository lookup that is not scoped or authorized. Read-only; no secrets in the output.
```
Step 2 (after you approve the plan, with `security-implementer`):
```text
Using the approved plan <paste or link>, add cross-user and cross-tenant negative tests for the routes listed, run them against the CURRENT code first and show the failures, then apply the minimal fix with the framework's native mechanism (Laravel Policy/Gate::authorize or Nest Guard + ability check), and rerun. Use only local/test data. Do not change unrelated code and do not weaken any existing check. Report the exact commands and outputs and separate Implemented / Tested / Unverified.
```

## 5. Rate limiting and abuse prevention
- **Agent / skill:** `security-architect` (design), `security-implementer` (build) / `rate-limiting`, `request-observability`, `bot-detection`
- **Scope:** login, OTP verify/resend, password reset, signup, expensive search.
- **Allowed:** read; after approval, native limiter + tests; detection rules in **observe** only.
- **Prohibited:** permanent bans, blocking on User-Agent/geography/score alone, enabling `enforce`, keying only on spoofable headers, load-testing a shared environment.
- **Evidence:** route class × limiter key × limit/window × behaviour on store failure; tests: N+1th request → 429 with `Retry-After`, reset after window, per-account key independent of IP, IPv6 `/64`, shared-IP fixture not blocked.
- **Acceptance:** every sensitive route has a tested limiter; client IP comes from trusted-proxy rules; any detection rule is `mode: observe`.

```text
Design the rate limiting for <login, OTP verify, password reset> in <repo> using the rate-limiting skill. First verify how the client IP is resolved (trusted proxies) and report if it is wrong.
Propose limiter keys (ip + normalized identifier for login; identifier + ip for OTP; /64 for IPv6), limits and windows from the legitimate peak rates you find, 429 with Retry-After and an identical response shape whether or not the account exists, and fail-open vs fail-closed per route class when the store is down.
Do not implement anything yet. List the tests you would write and any detection rule as mode: observe with its false-positive risks (shared NAT, mobile carriers). Wait for my approval.
```

## 6. Dependency and secret scanning
- **Agent / skill:** `security-auditor` (static review), `security-implementer` for CI jobs / `devsecops`, `security-audit`
- **Scope:** lockfiles, manifests, `.gitignore`, CI files, Dockerfiles; git history only if you ask.
- **Allowed:** read; run `composer audit` / `npm audit --omit=dev` **only if you have allowed that command** (the auditor has no shell tool; use the reviewer or implementer, or run it yourself and paste the output).
- **Prohibited:** printing a secret value, sending code or lockfiles to an external service, committing a baseline that hides real findings.
- **Evidence:** audit output as-is; list of suspected secrets as `path:line — type` only; CI permissions and action pins.
- **Acceptance:** no secret value anywhere in the report; every High+ dependency finding lists package, version, fix version; seeded-failure evidence for any new CI job (throw-away branch).

```text
Review dependency and secret hygiene of <repo> with the security-audit and devsecops skills, read-only.
Report: lockfiles present and committed; direct dependencies with known issues if I provide the output of composer audit / npm audit --omit=dev (do not run them unless I have allowed it); whether .env and key files are git-ignored; any hard-coded credential, token or key as "path:line — secret type" ONLY (never the value); CI workflows: permissions, unpinned third-party actions, pull_request_target usage, secrets in logs; Dockerfiles: root user, secrets in layers or build args.
Propose fixes as pointers to the devsecops skill; do not change files.
```

## 7. Security fix with regression tests
- **Agent / skill:** `security-implementer` / the skill matching the finding (`auth-hardening`, `api-security`, `rate-limiting`, …)
- **Scope:** the findings you list from an audit; **one finding at a time**.
- **Allowed:** read; edit the files named in the plan; run the project's tests (`verify_commands.tests`).
- **Prohibited:** touching files outside the plan, widening permission allow-lists, disabling existing checks, running anything against production, printing secrets, committing without review.
- **Evidence:** failing test first (or a justified reason), minimal diff, passing test output, full relevant suite result.
- **Acceptance:** each fix has a regression test that fails without the fix; the diff stays within the plan; Implemented / Tested / Unverified table present; nothing merged until the reviewer (example 8) approves.

```text
Start only if the plan below is approved by me. Plan: <paste plan or finding IDs>.
For finding <ID>: load the relevant skill, write a regression test that reproduces the issue and show it failing on the current code, apply the smallest fix using the framework's native mechanism, rerun the test and the related suite, and show the exact commands and outputs.
Keep changes within the plan; report anything out of scope instead of fixing it. Do not disable or weaken existing checks, do not touch permission lists, do not print secrets, do not commit. Finish with the skill's report format and an Implemented / Tested / Unverified table.
```
In Antigravity, run this on a throw-away branch: with `permission_mode: always-proceed` it will not ask before writing.

## 8. Independent reviewer verification
- **Agent / skill:** `security-reviewer` / `security-validation` — in a **new session**, not the implementer's.
- **Scope:** a diff or commit range.
- **Allowed:** read; run the relevant local tests (Claude: needs `Bash`, approve it per command).
- **Prohibited:** editing source, approving its own work, claiming a test passed without running it, running against production.
- **Evidence:** commands executed + results; authorization matrix for changed routes; redaction check; observe-only defaults; false-positive fixtures; regression review.
- **Acceptance:** verdict Approve / Approve with conditions / Reject; any open High/Critical ⇒ Reject; table that separates "executed" from "only read".

```text
Review the change <commit range or branch> as an independent security reviewer using the security-validation skill. You did not write it.
Read the plan, the diff and the tests. Run the relevant local test suites (<verify command>) and show exact commands and results. For each changed or new route verify authn, authz, object-level and tenant checks and that negative tests exist. Grep emitted events/logs in tests for seeded secrets. Confirm detection/response rules default to observe, with scope, expiry, idempotency and rollback. Try to bypass the fix using test fixtures only, against the local test app.
Do not edit any file. Distinguish what you executed from what you only read. End with a verdict (Approve / Approve with conditions / Reject), findings with severity and evidence, and Implemented / Tested / Unverified.
```

## 9. Security regression validation before release
- **Agent / skill:** `security-reviewer` (or `security-orchestrator` to sequence audit → validation) / `security-validation`, `devsecops`
- **Scope:** the release candidate commit/tag; staging or local only.
- **Allowed:** read; run the full local test suite and the dependency audit if allowed; compare with the previous audit.
- **Prohibited:** production access or data, deploying, tagging, changing code, enabling any blocking rule.
- **Evidence:** full-suite result; list of previously fixed findings with their regression tests still passing; dependency audit; secret scan result; config review (debug off, CORS, headers); rollback plan present.
- **Acceptance:** verdict with reasons; zero open High/Critical; every item marked executed vs not executed; unexecuted checks are not counted as passes.

```text
Run a pre-release security regression validation of <release candidate> using security-validation and devsecops. Local/staging only; no production access or data.
1) Run the full test suite and show the result. 2) For each previously reported finding <IDs or report path> confirm its regression test still exists and passes. 3) Review dependency audit output (<paste or run if allowed>), secret-scan result, debug flag, CORS, security headers, container user. 4) Check that detection rules are still observe-only unless I approved a promotion, and that a rollback procedure exists.
Do not change code or deploy. Report verdict (Approve / Approve with conditions / Reject), open findings by severity with evidence, and a table of Executed / Not executed / Unverified. A check you could not run is "not executed", never a pass.
```

## 10. Environment identification and mode selection (start here when a URL or deployment is involved)
- **Agent / skill:** `security-orchestrator` (or `security-auditor` for a static profile) / `environment-assessment`
- **Scope:** the repository plus `.security-engineering/assessment-scope.yaml`.
- **Allowed:** read files; record evidence, confidence, limits and ambiguities; run `assessment-gate.py classify/check` if a shell is available and you allow it.
- **Prohibited:** inferring the environment from a hostname/URL, inferring authorization from reachability, contacting any target, granting itself authorization.
- **Evidence:** environment profile (determined, confidence, evidence list, ambiguities), chosen mode, and for each planned active step the gate decision with rule ids.
- **Acceptance:** an ambiguous environment ends in `code-only` with the questions to the owner; no active step without gate `allow`.

```text
Before any audit, apply the environment-assessment skill to <repo>. Read the deployment manifests, CI deploy jobs, infrastructure definitions and environment configuration, and .security-engineering/assessment-scope.yaml.
Report: the environment (local / staging / production / unknown) with confidence and the evidence behind it; what is ambiguous; the authorized scope as recorded (approver, targets, activities, window, limits, test accounts); the mode you will use (code-only / local / staging / production); and, for each active test you would want, the gate decision (run assessment-gate.py check if you may, otherwise apply the skill's decision order and say so).
Do not treat a hostname or URL as evidence and do not treat reachability as authorization. Contact nothing. If anything is ambiguous, stay in code-only mode and list the questions I must answer.
```

## 11. Staging full-surface assessment (code + authorized deployed surface)
- **Agent / skill:** `security-orchestrator`, `security-auditor`, `security-reviewer` / `environment-assessment`, `security-audit`, `security-validation`
- **Scope:** only the targets in the recorded authorization, inside its window, within its request limit.
- **Allowed:** the code review; planning of DAST/API/fuzzing/TLS/header/CORS/cookie/rate-limit/authz-session checks; **executing them is done by you or an approved tool** — the agents have no network tool — with dedicated test accounts and synthetic data.
- **Prohibited:** any target outside the scope, real user accounts or data, exceeding limits, skipping stop conditions or rollback, exploitation, live enforcement.
- **Evidence:** matrix with every `staging` topic of `core/assessment-coverage.yaml`; raw outputs of the tests you ran; reproduction of each finding; retest after fix.
- **Acceptance:** `assessment-gate.py validate-report` has no problem; every PASS has evidence; untested topics are `NOT_TESTED` with a reason; a fixed finding is retested without regression.

```text
Run a staging full-surface assessment of <app> using environment-assessment. First confirm the environment from verifiable evidence and show me the gate decision for each planned activity class against each target (I will run the active tests myself or with an approved tool; you cannot send requests).
Plan the checks for TLS and certificates, security headers, CORS, cookies, DNS and exposed services, API/DAST tests, controlled fuzzing, negative authorization tests, session lifecycle, rate limiting and anti-automation, logging and alerting, and recovery controls, with request limits, stop conditions and rollback. Use only the test accounts <ids> and synthetic data.
When I give you results, build the assessment matrix (PASS only with evidence; missing evidence is NOT_TESTED), a reproduction and a retest for every finding, and finish with the five summary categories. Never say the application is secure.
```

## 12. Production security-posture assessment (non-destructive)
- **Agent / skill:** `security-orchestrator`, `security-reviewer` / `environment-assessment`, `incident-response`, `devsecops`
- **Scope:** existing configuration and telemetry you provide, plus only the read-only requests explicitly authorized.
- **Allowed:** reviewing configuration exports, existing logs/alerts, backup and recovery documentation; correlating them with the source code; read-only checks you run and paste.
- **Prohibited:** brute force, load or stress, exploitation, any account/session/firewall/IP change, data exfiltration, collecting more sensitive data than the minimum evidence, any target outside the scope.
- **Evidence:** matrix with every `production` topic; configuration excerpts (secrets redacted); explicit list of tests intentionally not performed and why.
- **Acceptance:** nothing is marked PASS without evidence; operational controls that could not be verified safely are `NOT_TESTED`; no enforcement action is proposed as something the agent did.

```text
Assess the production security posture of <app> using environment-assessment, non-destructively. I will paste configuration excerpts (secrets redacted), existing log/alert samples and backup/restore documentation; you will not run or request any state-changing, load or credential test.
Cover external exposure and TLS, security headers, effective authentication and authorization boundaries (from the code and the configuration I provide), cloud IAM and network segmentation, containers and supply chain, secrets management, rate limiting and abuse controls, logging, audit trails and alerting, incident-response readiness, and backups and recovery. Correlate each runtime observation with the source code.
Produce the assessment matrix (PASS requires evidence; otherwise NOT_TESTED with the reason), and list the tests intentionally not performed for safety or authorization reasons. Do not propose to lock accounts, revoke sessions or block IPs yourself; recommend them for human decision if justified. Never say the application is secure.
```

---

### Quick pairing table
| I want to… | Start | Example |
|---|---|---|
| know what is wrong | `security-auditor` | 1, 3, 6 |
| design before coding | `security-architect` | 2, 5 |
| fix an approved finding | `security-implementer` | 4 (step 2), 7 |
| verify someone else's work | `security-reviewer` (new session) | 8, 9 |
| know what environment this is and what may be tested | `security-orchestrator` (stage 0) | 10 |
| assess a deployed staging / production system | orchestrator + you running the active tests | 11, 12 |
| run the whole chain | `security-orchestrator` | any; delegation reliability differs by tool ([USER-GUIDE.md §4](USER-GUIDE.md#4-the-five-agents)) |
