---
name: security-audit
description: "Read-only security audit of a web/API codebase: maps entry points, auth and authorization boundaries, input handling, secrets, dependencies and logging, then reports evidenced findings with severity. Use before changing security controls or when asked \"is this secure?\"."
metadata:
  version: "0.1.0"
  category: assessment
---
# security-audit

## 1. Purpose
Produce an evidenced, severity-ranked list of vulnerabilities and missing controls without modifying the code.

## 2. When to invoke
Start of any security work; before a release; after a suspected incident; when onboarding a repo.

## 3. Preconditions
Read access to the repo. No production credentials. Confirm scope (whole repo or module) with the user if ambiguous.

## 4. Required discovery steps
1. Detect framework/version (`composer.json`, `package.json`, lockfiles) and read `.security-engineering/config.yaml` if present.
2. List all entry points: routes/controllers, webhooks, queue consumers, scheduled jobs, CLI, file uploads.
3. Identify authn mechanism (session, Sanctum/Passport, JWT, API keys) and authz mechanism (policies/gates, guards/CASL, ad-hoc checks).
4. Locate tenant boundary if multi-tenant.
5. List config surfaces: CORS, CSP/headers, cookies, trusted proxies, debug flags, CI/CD files, Dockerfiles.

## 5. Detailed workflow
1. For every entry point record: auth required? authz check? object-level ownership check? validation? rate limit? audit event?
2. Check OWASP API Top 10 (BOLA/IDOR, broken auth, property-level authz/mass assignment, resource consumption, function-level authz, SSRF, misconfig, inventory, unsafe API consumption) — see `references/checklist.md`.
3. Search for secrets, raw SQL concatenation, unsafe deserialization, `eval`, shell execution with user input, open redirects, weak crypto, disabled TLS verification.
4. Run dependency audit if the tool is available offline-safe (`composer audit`, `npm audit --omit=dev`); report as-is.
5. Rank by likelihood × impact; assign Critical/High/Medium/Low/Info.

## 6. Security constraints
Read-only. Never print secret values — report path + secret type only. Never exploit against non-local systems. Do not run state-changing requests.

## 7. Implementation requirements
None (no code changes). Output only the report; propose fixes as pointers to the relevant skill.

## 8. Test requirements
For each High/Critical finding give a reproducible check (request, test sketch or grep) that a future test can assert.

## 9. Failure handling
If framework cannot be detected, say so, audit generic controls only, mark framework items "unverified". If a command fails, report the error, do not retry blindly.

## 10. Completion criteria
Every entry point has a row in the coverage matrix; every finding has file:line evidence, severity, and remediation skill; unverified areas are listed.

## 11. Required report format
```
# Audit report — <repo> @ <commit>
Scope / Not covered
Coverage matrix: entry point | authn | authz | object-level | validation | rate-limit | audit
Findings: ID | Severity | Title | Evidence(file:line) | Impact | Fix (skill) | Verification
Unverified items
Summary: counts by severity
```
