---
name: environment-assessment
description: "Identify whether a target is local, staging, production or unknown from verifiable evidence, record the authorized scope, pick the matching assessment mode (code audit, full-surface staging, production posture) and report an evidence-based control matrix. Use first, before any audit or active test."
metadata:
  version: "0.1.0"
  category: assessment
---
# environment-assessment

## 1. Purpose
Choose the assessment depth the environment and the authorizations really allow, and never report more than was verified. A code audit does not validate a deployed system.

## 2. When to invoke
Before `security-audit`, `security-validation`, or any request that mentions a URL, a deployment, "staging", "production", DAST, scanning, load or brute-force testing. The orchestrator runs it as stage 0.

## 3. Preconditions
Read access to the repository and its deployment/CI files. No production credentials. Scope and authorization come from a human owner and are recorded in `.security-engineering/assessment-scope.yaml` (template: `adapters/project/assessment-scope.yaml.template`, schema: `contracts/assessment-scope.schema.json`).

## 4. Required discovery steps
1. Identify repository, application, framework, deployment architecture and which accesses exist (code only? a URL? accounts? telemetry?).
2. Collect **verifiable** evidence of the environment: deployment manifests, CI/CD deploy jobs, infrastructure definitions, environment configuration, runtime metadata. Record each as `kind` / `detail` / `supports`.
3. Record what the owner declares, and the explicit authorization: approver, targets (domains, IP ranges, URLs), allowed activity classes, test window, request-rate limit, stop conditions, rollback, dedicated test accounts.
4. Note confidence, evidence, limitations and unresolved ambiguities.

## 5. Detailed workflow
1. **Never infer the environment from a name.** A hostname or URL containing "staging", "test" or "dev" is not evidence. **Never infer authorization from technical accessibility** (a reachable host is not a permitted target). An owner's declaration alone is not enough either; it only corroborates verifiable artefacts. Conflicting signals ⇒ environment `unknown`; if any evidence points at production, treat heavy activities as denied until resolved.
2. Classify with the deterministic gate when a shell is available: `python3 <gate> classify .security-engineering/assessment-scope.yaml`; for each active activity you plan, `python3 <gate> check <scope> --activity <class> --target <t> --now <UTC time given by the operator>`. `<gate>` is `scripts/assessment-gate.py` in the toolkit repository and `.security-engineering/shared/scripts/assessment-gate.py` in an installed project (`~/.security-engineering/shared/scripts/` for a global install); it needs python3 + PyYAML. Exit 0 = allow, 3 = needs_confirmation, 1 = deny. Agents without a shell apply the same rules below; the human or CI runs the gate to confirm. The gate, not your judgment, decides.
3. Select the mode:

| Environment | Mode | What it is |
|---|---|---|
| unknown / ambiguous | `code-only` | non-destructive code and configuration analysis; ask before any active test |
| local | `local` | static audit: threat model; OWASP Top 10, API Top 10 and relevant ASVS; authn/authz/RBAC/session/business logic; validation, injection, SSRF, IDOR/BOLA, deserialization, file handling, crypto; dependencies, secrets, containers, IaC, CI/CD; focused security, negative and regression tests; list what cannot be verified without a deployment |
| staging | `staging` | code **plus** the authorized deployed surface: discovery, TLS/certs/headers/CORS/cookies/DNS/exposed services, DAST and API tests, controlled fuzzing, negative authorization tests, session and recovery flows, rate limiting and anti-automation, proxy/WAF/containers/storage, logging and alerting, reproducibility of findings. Dedicated test accounts and synthetic data; request limits, window, stop conditions, rollback |
| production | `production` | operational posture, non-destructive: external surface, effective authn/authz/sessions, headers/TLS, cloud IAM and segmentation, containers and supply chain, secrets management, rate limiting and abuse controls, logs/alerts/IR/backups/recovery readiness, correlation of runtime observations with source findings, read-only requests and existing telemetry |

4. **Decision order** (first match wins; the gate applies the same order): unknown activity class ⇒ deny · `exploitation`/`enforcement_action` ⇒ deny · `static_analysis`/`passive_observation` ⇒ allow · environment unknown ⇒ `needs_confirmation` (heavy activities ⇒ deny if anything points to production) · confirmed local + loopback target ⇒ allow · no explicit attributed authorization ⇒ deny · target not in scope ⇒ deny · class not in `allowed_activities` ⇒ deny · outside the window ⇒ deny · missing limits ⇒ `needs_confirmation` · rate over cap ⇒ deny · missing test accounts ⇒ `needs_confirmation` · production heavy activity without a valid exception ⇒ deny · otherwise allow. The time to use is the one the operator gives; if none is given or it contradicts the system clock, ask.
   Activity classes (the gate's vocabulary): `static_analysis`, `passive_observation` (no request to any target) are always allowed. `active_read_only`, `active_authenticated`, `active_fuzzing`, `active_load`, `active_state_changing`, `sensitive_data_collection` need a confirmed environment, explicit attributed authorization, an in-scope target, the class in `allowed_activities`, a window, limits and (when authenticated or state-changing) test accounts. Rate caps: local 200, staging 50, production 5 requests/second. `exploitation` and `enforcement_action` (account lock, session revocation, firewall or IP block) are **never** initiated by an agent. In production, `active_fuzzing`, `active_load`, `active_state_changing` and `sensitive_data_collection` additionally need a specific, attributed, unexpired `production_exception` with a safety plan.
5. Production defaults: no destructive exploitation, no denial-of-service or stress test, no real-user credential attacks (no brute force), no account or business-record changes, no data exfiltration, no sensitive data beyond the minimum evidence, nothing outside the approved scope. Where a safe check is impossible, the control is `NOT_TESTED`, never a pass.
6. Build the **assessment matrix**: one row per control with `topic` (see `core/assessment-coverage.yaml`: every topic of the mode must appear), control, environment, verification scope (`static`/`dynamic`/`operational`), method, evidence, result `PASS|FAIL|PARTIAL|NOT_TESTED|NOT_APPLICABLE`, severity, confidence, remediation, retest. **PASS needs sufficient evidence**; missing evidence is never a pass. A code-only or local assessment cannot PASS an operational control (real server config, network controls, production TLS, cloud IAM, runtime monitoring).
7. Fill the final summary with the five categories: verified secure controls · confirmed vulnerabilities · partially verified · unverified controls and environmental limitations · tests intentionally not performed (safety or authorization). Never say the application is "secure" or "completely secure" because nothing was found.

## 6. Security constraints
Read-only on source. No secret values in the scope file, matrix or report (path and type only). No contact with any target unless the gate returned `allow` for that exact activity and target. An agent never grants itself or others authorization, never widens scope, never overrides the gate, and never authorizes enforcement; observe-only runtime policies stay observe-only.

## 7. Implementation requirements
None for application code. The deterministic logic lives in `scripts/assessment-gate.py` (installed under `<shared>/scripts/`); the agents need no new tool or permission. Active tests are executed by a human or an approved tool, not by the read-only agents.

## 8. Test requirements
Repository tests (`tests/assessment`) cover environment classification, every gate rule, the report validator and its coverage topics. For an application: each FAIL row has a retest procedure that a future regression test can assert.

## 9. Failure handling
Ambiguous, conflicting or missing evidence ⇒ environment `unknown`, mode `code-only`, ask the owner before any active test. A gate answer of `needs_confirmation` means stop and ask; `deny` means do not do it, and say what was not performed. If the gate cannot be run, apply the rules conservatively and say so.

## 10. Completion criteria
Environment, confidence, evidence and ambiguities recorded; mode justified; every active step backed by a gate `allow`; matrix contains every topic of the mode; `python3 scripts/assessment-gate.py validate-report <report.json>` reports no problems (or the report states it was not run).

## 11. Required report format
```
Environment profile: determined | confidence | evidence | ambiguities | limitations
Scope & authorization: approver | targets | activities | window | limits | test accounts
Mode and gate decisions (activity, target, decision, rule ids)
Matrix: topic | control | environment | scope | method | evidence | result | severity | confidence | remediation | retest
Summary: verified secure | confirmed vulnerabilities | partially verified | unverified + limitations | intentionally not performed
```
