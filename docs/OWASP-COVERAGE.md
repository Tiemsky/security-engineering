# OWASP coverage matrix

**This is a traceability matrix, not a compliance claim.** The toolkit does not make an application compliant with, or "covered by", any OWASP list. Nearly everything below is *guidance an agent follows while working on your code*; very little is code that this repository ships and tests.

Built by reading every `skills/*/SKILL.md`, `skills/security-audit/references/checklist.md`, `policies/*.yaml`, `contracts/*.json`, `adapters-runtime/**`, `agents/manifest.json` and the test-suite (`tests/`), on 2026-10-16 for toolkit version 0.1.0. Keyword matches were not used as evidence: a row is justified by what the skill actually instructs or what a test actually executes.

## 1. How to read the status

| Status | Meaning in this document |
|---|---|
| `IMPLEMENTED_AND_TESTED` | Code in **this repository** implements it **and** an automated test executes it (for the runtime: on real Laravel 12.70 and NestJS 11.2 in Docker). It does *not* mean your application has it: the runtime is a reference you must wire in (`docs/project-integration.md`), and no pilot on a real application has run. |
| `IMPLEMENTED_NOT_VERIFIED` | Implemented here but its effect was never exercised. |
| `GUIDANCE_ONLY` | A skill/policy tells the agent to check or build it. Nothing in this repo implements it, and no test applies it to an application. Whether it happens depends on the agent, the model and your review. |
| `PARTIAL` | Some part is implemented and tested here; the rest is guidance or missing (see Limitations). |
| `MISSING` | No skill, policy or runtime addresses it beyond, at most, a bare mention. |
| `NOT_APPLICABLE` | Outside the scope of the toolkit (server-side Laravel/NestJS APIs). |

Three levels must not be confused: a **prompt instruction** (guidance) ≠ an **implemented control** (code) ≠ a **tested control** (a test that fails when the control is removed). What tests exist for the *skills* is limited to structure: `tests/skills/test_skills.py` checks that each skill has its 11 sections, valid metadata, resolvable references and a mention of testable acceptance — it does **not** check that a skill, when followed, produces a secure application. The agents' read-only boundaries are tested (`tests/agents/test_agents.py`) and were observed in real sessions; the *quality* of an audit or fix produced by an agent was not measured.

Standard versions and IDs, as read from the official sources on 2026-10-16: OWASP Top 10:2025 (`top10.owasp.org/2025`), OWASP API Security Top 10:2023, OWASP ASVS 5.0.0 (chapters V1–V17 from the `v5.0.0` tag), OWASP WSTG (stable = v4.2). ASVS is mapped at **chapter** level only: requirement-level (e.g. `v5.0.0-6.x.y`) traceability has not been done and would be the next step.

Evidence paths below are relative to the repository root. "Scenario X" means `tests/fixtures/scenarios/<X>.json`, replayed identically on Laravel and NestJS by `tests/integration/test_runtime.py`.

## 2. Reference-runtime controls (the only `IMPLEMENTED_AND_TESTED` items)
These are the pieces that actually run. All start in `observe`; none blocks anything until you promote a rule.

| ID | Control | Evidence | Status | Limitations |
|---|---|---|---|---|
| RT-01 | Client IP resolved only through trusted proxies; IPv4/IPv6 canonicalised, `/64` aggregation, zone ids and garbage rejected, spoofed `X-Forwarded-For` from an untrusted peer ignored | scenarios `client-ip-trust`, `client-ip-edge`, `stuffing-ipv6-prefix64`; `adapters-runtime/laravel/src/ClientIp.php`, `adapters-runtime/nestjs/src/ip.ts` | `IMPLEMENTED_AND_TESTED` | correct only if `trusted_proxies` matches your topology |
| RT-02 | Redaction of forbidden keys and value patterns (passwords, OTP, tokens, cookies, JWT, bearer, PAN-like, API keys) before any sink; no body capture; query values dropped | `policies/redaction.yaml`; scenarios `secrets-redaction`, `secret-in-signal`; `tests/policies/test_policies.py` (`test_redaction_policy_blocks_forbidden_data_but_not_uuids`) | `IMPLEMENTED_AND_TESTED` | pattern-based safety net; callers should pass opaque identifiers; not a DLP product |
| RT-03 | Structured `http_access` / `security_*` / `system_health` events validated against JSON Schemas; route **template**, request id | `contracts/*.schema.json`; `tests/contracts/test_contracts.py`; `tests/integration/test_runtime.py`; `adapters-runtime/laravel/src/HttpAccessMiddleware.php` | `IMPLEMENTED_AND_TESTED` | sinks are in-memory/log in the harness; no durable store; W3C `traceparent` (named in `request-observability`) is **not** implemented — only `X-Request-Id` |
| RT-04 | 7 deterministic detection rules + 8 signals, each with a triggering and a below-threshold case; coverage guard fails if a rule loses its scenario | `policies/detection-rules.yaml`; scenarios `rule-*`, `stuffing-observe`, `window-edge-*`; `tests/integration/test_scenario_coverage.py` | `IMPLEMENTED_AND_TESTED` | signals must be fed by the application's own code (login/OTP/webhook/404 handlers); the middleware does not derive them; thresholds are untuned defaults; false-positive rate on real traffic unmeasured |
| RT-05 | Observe / alert / enforce / manual_review separation; sole-signal rule (UA, geo, score never alone); shared-IP exception ⇒ `manual_review`; approval gates; TTL-bounded actions | `policies/defaults.yaml`, `policies/response-actions.yaml`; scenarios `mode-alert`, `shared-nat-no-block`, `enforce-and-expire`, `rule-honeypot-shared-ip`; `tests/policies/test_policies.py` | `IMPLEMENTED_AND_TESTED` | enforce acts on IP / `/64` scopes via a 429 gate only |
| RT-06 | `account_lock`, `session_revocation`, `challenge` are never executed (always `manual_review` + `pending_approval`) | scenario `never-executes-risky-actions` | `IMPLEMENTED_AND_TESTED` (as a refusal) | the executors themselves **do not exist** — see MISSING items below |
| RT-07 | Idempotency, retry ≤3 after failed action, rollback, duplicate suppression, expiry edges | scenarios `rollback-flow`, `retry-after-recovery`, `repeat-attack-new-window`, `expiry-boundary`, `stuffing-observe` | `IMPLEMENTED_AND_TESTED` | single-process memory: restart loses windows and blocks; counters diverge across instances; no Redis/worker |
| RT-08 | Failure isolation: sink outage, store outage (fail-open), malformed signals rejected and counted, bounded memory under flood | scenarios `sink-failure-survives`, `enforce-store-failure-fail-open`, `malformed-signals`, `flood-bounded-memory` | `IMPLEMENTED_AND_TESTED` | credential endpoints are specified fail-closed in `policies/defaults.yaml` but no limiter exists in the runtime to apply it |
| RT-09 | Identical decisions on Laravel and NestJS for the same input | `tests/integration/compare.py`; 33 scenarios × 2 frameworks | `IMPLEMENTED_AND_TESTED` | tested on Laravel 12.70 / NestJS 11.2 only |

Not implemented in v0.1.0 (stated plainly): Redis or other shared state, background workers/queued sinks, real account-lock / session-revocation / challenge executors, a per-route rate limiter, webhook-signature verification code, an append-only audit store, Laravel Policy / NestJS Guard reference examples.

## 3. OWASP Top 10:2025

| ID | Risk and attack scenario | Skill / policy | Expected mitigation | Evidence | Status | Limitations / remediation |
|---|---|---|---|---|---|---|
| A01:2025 Broken Access Control (includes SSRF) | user of tenant B reads tenant A's object by id; admin route reachable by a normal user; server fetches an internal URL supplied by a user | `auth-hardening`, `api-security`, `security-audit`, `bot-detection` | central policy per resource, object-level checks, deny by default, tenant scope, SSRF guard (scheme allow-list, resolve then block private/metadata ranges) | rule `enum.sequential-ids` (scenario `rule-sequential-ids`) detects id walking; audit `references/checklist.md` lists BOLA and SSRF checks | `PARTIAL` | detection of enumeration is tested; the authorization/SSRF controls are guidance only; no Policy/Guard example code; **remediation**: add reference Policy/Guard + cross-tenant tests, then run a pilot |
| A02:2025 Security Misconfiguration | `APP_DEBUG=true`, wildcard CORS with credentials, exposed admin/telescope/swagger, missing headers | `security-audit` (checklist), `api-security`, `devsecops` | debug off, explicit CORS allow-list, HSTS/`nosniff`/frame protection/CSP, non-root containers | none beyond skill text and `tests/skills` (structure only) | `GUIDANCE_ONLY` | no config scanner is shipped; agents only read config; **remediation**: a configuration-checking test in the pilot |
| A03:2025 Software Supply Chain Failures | vulnerable or malicious dependency; unpinned CI action; secret in a layer | `devsecops`, `security-audit` (step 4) | `composer audit` / `npm audit --omit=dev` failing on High; pinned actions by SHA; secret scanning; minimal containers | none for the application. Toolkit itself: test images are pinned (see §8) | `GUIDANCE_ONLY` | the auditor has no network or shell tool, so it cannot run `composer audit` itself; the reviewer/implementer can only if you allow Bash; no secret scanner is bundled |
| A04:2025 Cryptographic Failures | weak password hashing, custom crypto, disabled TLS verification, tokens stored in clear | `auth-hardening`, `api-security`, `security-audit` (step 3) | argon2id/bcrypt, constant-time compare, hashed tokens/OTP, no custom crypto, TLS verification on | none (text only) | `GUIDANCE_ONLY` | no key-management, encryption-at-rest or TLS-configuration guidance |
| A05:2025 Injection | SQL injection via string-built queries, command/template injection, XSS | `api-security` (validation, "no raw SQL with interpolation"), `security-audit` (grep step) | native validation (FormRequest/DTO), parameterised queries, grep for `eval`/shell with user input | none | `GUIDANCE_ONLY` | narrow: no XSS, output-encoding, command or template-injection procedure; **remediation**: add an `injection` skill with negative tests |
| A06:2025 Insecure Design | missing abuse-case thinking; business-flow abuse | `threat-modeling` (STRIDE + abuse cases), `bot-detection` | scored threats ≥4 mapped to mitigation, skill, signal and test | agent boundary tests only (`tests/agents`); quality of generated models unmeasured | `GUIDANCE_ONLY` | threat-model content depends on the model and your review |
| A07:2025 Authentication Failures | credential stuffing, OTP brute force, user enumeration, session fixation, weak reset | `auth-hardening`, `rate-limiting`, `bot-detection` | throttled login/reset/OTP, uniform errors, session regeneration, OTP rules, observability events | detection rules `authn.stuffing-ip`, `authn.account-spray`, `otp.verify-bruteforce` (scenarios `stuffing-observe`, `rule-account-spray`, `rule-otp-bruteforce`) | `PARTIAL` | detection tested in observe; the hardening itself (hashing, throttling, MFA, session handling) is guidance; no account-lock executor |
| A08:2025 Software or Data Integrity Failures | forged webhook, replayed callback, unsigned update, unsafe deserialization | `api-security` (HMAC webhooks, timestamp, idempotency), `audit-trail` (hash chain), `security-audit` | HMAC over raw body, replay window, idempotency store, append-only audit | rule `webhook.bad-signature` (scenario `rule-webhook-bad-signature`) detects repeated bad signatures | `PARTIAL` | verification code is guidance; the runtime only counts failures reported by the app; deserialization is only a grep item in the audit; CI/artifact signing not covered |
| A09:2025 Security Logging and Alerting Failures | attack goes unnoticed; secrets leak into logs; logs tampered | `request-observability`, `audit-trail`, `incident-response`, `policies/redaction.yaml` | structured redacted events, correlation id, alerting on rules, append-only audit, runbooks | RT-02, RT-03, RT-04, RT-08; `contracts/audit-event.schema.json` (schema only) | `PARTIAL` | events are emitted in the harness; no delivery to a SIEM/pager; the audit store, hash chain and runbooks are guidance; `traceparent` not implemented |
| A10:2025 Mishandling of Exceptional Conditions | logging/detector failure breaks requests; stack traces to clients; fail-open on a credential check | `request-observability`, `api-security` (errors), `rate-limiting` (store failure), `policies/defaults.yaml` `failure_mode` | observability never fails a request; generic errors + correlation id; defined fail-open / fail-closed per route class | RT-08 (engine and sink failure) | `PARTIAL` | engine behaviour tested; error-body hygiene and fail-closed credential limiters are guidance (no limiter shipped) |

## 4. OWASP API Security Top 10:2023

| ID | Risk and attack scenario | Skill / policy | Expected mitigation | Evidence | Status | Limitations / remediation |
|---|---|---|---|---|---|---|
| API1:2023 Broken Object Level Authorization | `GET /orders/{id}` returns another user's order | `auth-hardening`, `security-audit`, `bot-detection` | authorize the *object* in every action; tenant scope; IDOR tests across users and tenants | rule `enum.sequential-ids` (`rule-sequential-ids`) | `PARTIAL` | same as A01 |
| API2:2023 Broken Authentication | stuffing, token theft, weak reset, no rate limit | `auth-hardening`, `rate-limiting`, `bot-detection` | see A07; rotating refresh tokens with reuse detection, hashed tokens | A07 rules | `PARTIAL` | as A07 |
| API3:2023 Broken Object Property Level Authorization | mass assignment of `is_admin`; response leaks `password_hash` | `api-security` | `$fillable`/`$guarded`, DTO `whitelist`+`forbidNonWhitelisted`, API Resources / serializers with allow-lists | none | `GUIDANCE_ONLY` | tests are only prescribed ("unknown field rejected") |
| API4:2023 Unrestricted Resource Consumption | login/OTP/search hammered; huge pages or uploads | `rate-limiting`, `api-security` (limits), `bot-detection` | layered limiter keys (ip+identifier, `/64`), 429 + `Retry-After`, body/page/upload caps | rules `scan.not-found-burst`, `otp.verify-bruteforce`, extra `request_rate_per_key` (`rule-request-rate`); `flood-bounded-memory` (the engine's own memory) | `PARTIAL` | runtime detects and, in enforce, 429-blocks IPs; **no per-route limiter is shipped** — the skill relies on native `RateLimiter`/`ThrottlerModule` written by the implementer |
| API5:2023 Broken Function Level Authorization | normal user calls an admin endpoint | `auth-hardening`, `security-audit` | deny by default, central policies, "admin route as non-admin = 403" test | none | `GUIDANCE_ONLY` | |
| API6:2023 Unrestricted Access to Sensitive Business Flows | automated abuse of signup / OTP / scraping / pricing | `bot-detection`, `threat-modeling` (abuse cases), `rate-limiting` | behavioural rules in observe first, human promotion, no UA/geo-only blocking | rules and scenarios under A07; `tests/policies/test_policies.py` (`test_no_rule_blocks_on_supporting_signals_alone`) | `PARTIAL` | business-specific flows must be modelled per application |
| API7:2023 Server Side Request Forgery | user URL makes the server call `169.254.169.254` or internal hosts | `api-security`, `security-audit` | scheme allow-list, resolve-then-block private/loopback/link-local/metadata, redirect re-validation, payload tests | none | `GUIDANCE_ONLY` | no shared SSRF helper exists in the repo (the skill says to create one) |
| API8:2023 Security Misconfiguration | permissive CORS, verbose errors, missing headers | `api-security`, `security-audit`, `devsecops` | see A02 | none | `GUIDANCE_ONLY` | |
| API9:2023 Improper Inventory Management | forgotten old API version or debug route | `security-audit` | every entry point gets a row in the coverage matrix (routes, webhooks, jobs, uploads) | none | `GUIDANCE_ONLY` | static inventory only; no version/deprecation tracking |
| API10:2023 Unsafe Consumption of APIs | trusting a third-party response or webhook payload | `security-audit` (named in the checklist), `api-security` (webhooks) | validate third-party data; signed webhooks | none | `MISSING` | named in the audit step only; no implementation guidance |

## 5. OWASP ASVS 5.0.0 (chapter level)

| ID | Risk (summary) | Skill / policy | Evidence | Status | Limitations / remediation |
|---|---|---|---|---|---|
| V1 Encoding and Sanitization | injection, XSS from unsanitised data | `api-security` (validation, no raw SQL) | none | `GUIDANCE_ONLY` | no output-encoding/sanitisation procedure |
| V2 Validation and Business Logic | unvalidated input, logic abuse | `api-security`, `threat-modeling`, `bot-detection` | none | `GUIDANCE_ONLY` | business-logic limits are per application |
| V3 Web Frontend Security | CSP, cookie flags, DOM issues | `api-security` (headers, CORS), checklist (cookies) | none | `GUIDANCE_ONLY` | no front-end (React/Vue) guidance |
| V4 API and Web Service | method/schema abuse, GraphQL depth | `api-security` | none | `GUIDANCE_ONLY` | WebSocket/GraphQL covered by a single mention |
| V5 File Handling | malicious upload, path traversal | `api-security` (uploads) | none | `GUIDANCE_ONLY` | no AV integration; "optional" in the skill |
| V6 Authentication | stuffing, weak credentials, OTP | `auth-hardening`, `rate-limiting`, `bot-detection` | A07 rules | `PARTIAL` | as A07 |
| V7 Session Management | fixation, no server-side logout | `auth-hardening` | none; `session_revocation` is never executed (RT-06) | `GUIDANCE_ONLY` | |
| V8 Authorization | missing object/function checks | `auth-hardening` | none | `GUIDANCE_ONLY` | no Policy/Guard example |
| V9 Self-contained Tokens | JWT misuse | `auth-hardening` (short-lived, rotating refresh, hashed storage) | none | `GUIDANCE_ONLY` | no algorithm/claims-validation detail |
| V10 OAuth and OIDC | redirect/flow flaws | — | — | `MISSING` | no skill covers OAuth/OIDC flows |
| V11 Cryptography | weak primitives | `auth-hardening`, checklist | none | `GUIDANCE_ONLY` | |
| V12 Secure Communication | TLS misconfiguration | `api-security` (HSTS, no disabled TLS verification) | none | `GUIDANCE_ONLY` | |
| V13 Configuration | secrets in code, debug flags | `devsecops`, `security-audit`, `PROJECT_RULES` | `tests/skills` checks only that references/secrets patterns are absent from the skills themselves | `GUIDANCE_ONLY` | no secret scanner bundled |
| V14 Data Protection | sensitive data in logs/responses/caches | `request-observability`, `api-security`, `audit-trail` | RT-02 | `PARTIAL` | redaction of emitted events tested; response filtering and cache headers are guidance |
| V15 Secure Coding and Architecture | dependency risk, design flaws | `devsecops`, `threat-modeling`, `framework-adapter-development` | none for the application | `GUIDANCE_ONLY` | |
| V16 Security Logging and Error Handling | missing/leaky logs, error disclosure | `request-observability`, `audit-trail`, `api-security` | RT-02, RT-03, RT-08 | `PARTIAL` | see A09/A10 |
| V17 WebRTC | media-session security | — | — | `NOT_APPLICABLE` | toolkit targets HTTP APIs |

## 6. OWASP WSTG test categories (v4.2)
The agents have **no network or dynamic-testing tool**; they read code and run only the commands you allow. The WSTG is therefore mapped as "what the skills ask the agent to check in code or to test locally", not as executed penetration tests. The `environment-assessment` skill now defines *when* a staging or production test is permitted (explicit scoped authorization, limits, window, caps) and what the report must contain; it does not ship a scanner, so dynamic WSTG categories remain `GUIDANCE_ONLY` and require a human or an approved tool to execute.

| ID | Category | Skill / policy | Evidence | Status | Limitations |
|---|---|---|---|---|---|
| WSTG-INFO | Information Gathering | `security-audit` (entry-point discovery), `environment-assessment` (environment profile) | none | `GUIDANCE_ONLY` | static discovery of the code, not black-box |
| WSTG-CONF | Configuration and Deployment Management | `security-audit`, `devsecops` | none | `GUIDANCE_ONLY` | |
| WSTG-IDNT | Identity Management | `auth-hardening` (enumeration-safe responses) | rule `enum.sequential-ids` for id walking | `PARTIAL` | account enumeration prevention is guidance |
| WSTG-ATHN | Authentication | `auth-hardening`, `rate-limiting` | A07 rules | `PARTIAL` | |
| WSTG-ATHZ | Authorization | `auth-hardening`, `security-validation` | none | `GUIDANCE_ONLY` | negative IDOR tests are prescribed, not provided |
| WSTG-SESS | Session Management | `auth-hardening` | none | `GUIDANCE_ONLY` | |
| WSTG-INPV | Input Validation | `api-security` | none | `GUIDANCE_ONLY` | |
| WSTG-ERRH | Error Handling | `api-security` | RT-08 (engine) | `PARTIAL` | client-facing error hygiene is guidance |
| WSTG-CRYP | Weak Cryptography | `auth-hardening` | none | `GUIDANCE_ONLY` | |
| WSTG-BUSL | Business Logic | `threat-modeling`, `bot-detection` | none | `GUIDANCE_ONLY` | |
| WSTG-CLNT | Client-side | — | — | `MISSING` | no front-end guidance |
| WSTG-APIT | API Testing | `api-security` (negative tests), `security-validation` ("try to break it" on the local test app) | none | `GUIDANCE_ONLY` | no scanner or fuzzer shipped |

## 7. Laravel- and NestJS-specific controls

| ID | Control (framework mechanism) | Where it comes from | Evidence | Status | Limitations |
|---|---|---|---|---|---|
| FW-L01 | Laravel request middleware + `terminate()` emitting events, request id, enforcement gate | `adapters-runtime/laravel/src/HttpAccessMiddleware.php`, `SecurityEngineeringServiceProvider.php` | real Laravel 12.70 in Docker (`tests/integration/run_laravel.sh`) | `IMPLEMENTED_AND_TESTED` | wired in a throw-away app only |
| FW-N01 | NestJS middleware + `AccessInterceptor` + `AccessExceptionFilter` + `SecurityModule` | `adapters-runtime/nestjs/src/` | real NestJS 11.2 in Docker (`tests/integration/run_nestjs.sh`) | `IMPLEMENTED_AND_TESTED` | same |
| FW-L02 | FormRequest validation; `$fillable`/`$guarded` not `[]`; API Resources | `api-security`, checklist | none | `GUIDANCE_ONLY` | |
| FW-N02 | `ValidationPipe({whitelist, forbidNonWhitelisted, transform})`; DTOs; serializers | `api-security`, checklist | none | `GUIDANCE_ONLY` | |
| FW-L03 | Policies / `Gate::authorize`, tenant global scope | `auth-hardening` | none | `GUIDANCE_ONLY` | reference Policy example is `MISSING` |
| FW-N03 | Guards, `@nestjs/passport`/JWT, ability checks | `auth-hardening` | none | `GUIDANCE_ONLY` | reference Guard example is `MISSING` |
| FW-L04 | `RateLimiter::for()` + `throttle:` middleware, Sanctum/Fortify | `rate-limiting`, `auth-hardening` | none | `GUIDANCE_ONLY` | |
| FW-N04 | `@nestjs/throttler` with custom `getTracker`, Redis storage | `rate-limiting` | none | `GUIDANCE_ONLY` | the runtime itself has no Redis |
| FW-L05 | `APP_DEBUG=false`, trusted-proxy configuration | checklist, `request-observability` | trusted-proxy logic of the runtime: RT-01 | `PARTIAL` | application config is not checked by any test |
| FW-L06 | `composer audit` | `devsecops`, `security-audit` | none | `GUIDANCE_ONLY` | |
| FW-N05 | `npm audit --omit=dev` | `devsecops`, `security-audit` | none | `GUIDANCE_ONLY` | |

## 8. Toolkit self-protection (the agents and installer, not your application)

| ID | Control | Evidence | Status | Limitations |
|---|---|---|---|---|
| TK-01 | Read-only agents have no write tool in any of the three tools; implementer is the only writer and asks first where the tool allows | `tests/agents/test_agents.py`; real sessions (validation §2) | `IMPLEMENTED_AND_TESTED` | Claude reviewer has `Bash` (L1); Antigravity cannot enforce confirmation (L4) |
| TK-02 | Installer integrity: sha256-tracked manifest, conflicts not overwritten, backups, version pin, uninstall removes only what it created | `tests/installer/` | `IMPLEMENTED_AND_TESTED` | macOS/native Windows not run |
| TK-03 | Pinned test images and dependencies (PHP 8.4.26, Laravel 12.70.0, Node 24.21.0, NestJS 11.2.7, PowerShell 7.4, opencode-ai 1.19.2) | `tests/integration/docker/`; fresh-clone rebuild: 71 tests green | `IMPLEMENTED_AND_TESTED` | Docker base images are pinned by tag, not by digest |
| TK-04 | CI workflow running the test-suite | `.github/workflows/ci.yml` | `IMPLEMENTED_NOT_VERIFIED` | never run on a hosted runner; actions not pinned by SHA |
| TK-05 | Antigravity rule file nudging the agent to follow the workflow | `adapters/antigravity/rules/security-engineering.md` (frontmatter validity tested) | `IMPLEMENTED_NOT_VERIFIED` | its effect on behaviour was never observed |
| TK-07 | Environment identification and scope gate: only verifiable evidence decides local/staging/production; no active test without explicit scoped authorization; exploitation and enforcement never agent-initiated; production caps; report validator (PASS needs evidence, no "secure" claim) | `scripts/assessment-gate.py`; `tests/assessment` (30 tests: 13 scenarios, every rule exercised, 6 injected defects detected); real sessions on three tools, 4 scenarios each | `IMPLEMENTED_AND_TESTED` | the agents cannot run active tests (no network tool); model behaviour is checked on 4 scenarios, one run each; hostnames/artefact kinds are an enumerated list, not a discovery tool |
| TK-06 | No secrets in skills, agents or fixtures | `tests/skills`, `tests/installer` (`test_no_secrets_copied`) | `IMPLEMENTED_AND_TESTED` | pattern-based |

## 9. Gaps, in priority order
1. **No application-side evidence.** Every `GUIDANCE_ONLY` row becomes real only after an agent implements it in a project *and* tests show it. Next step: Pilot A (read-only audit) then a fix cycle with negative tests on a test project.
2. Missing reference code: Laravel Policy / NestJS Guard, SSRF guard, webhook verifier, per-route limiter, audit store (all prescribed by skills, none shipped).
3. Missing skills: injection/XSS/output encoding, OAuth/OIDC, front-end, unsafe API consumption, cryptography/key management.
4. Active-test tooling: an approved DAST/fuzzing procedure that a human can run inside the gate's limits; ASVS requirement-level traceability (chapter level only today) and a real WSTG dynamic-test procedure.
5. Runtime limits: shared state (Redis) and workers; `traceparent`; real account-lock / session-revocation / challenge executors with approval flow.

*Maintenance rule:* when a skill, policy or runtime control changes, update the row and its status in the same commit. `tests/docs/test_docs.py` checks that every status is one of the six values, that cited paths exist, and that every scenario named here exists.
