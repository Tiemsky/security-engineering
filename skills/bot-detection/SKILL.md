---
name: bot-detection
description: "Design and implement deterministic, evidence-based detection rules for automated abuse (credential stuffing, enumeration, scraping, scanners) that start in observe-only mode. Use when asked to detect or block bots."
metadata:
  version: "0.1.0"
  category: implementation
---
# bot-detection

## 1. Purpose
Detect abusive automation via versioned rules over structured events, with measurable false-positive rates.

## 2. When to invoke
Abuse observed or anticipated on login, OTP, signup, search, pricing, or enumerable IDs.

## 3. Preconditions
`request-observability` events flowing; `rate-limiting` baseline exists or is planned; `policies/` readable.

## 4. Required discovery steps
Identify abuse targets, legitimate traffic shapes (mobile apps, shared NAT/carrier IPs, office networks, monitoring), existing exceptions.

## 5. Detailed workflow
1. Write each rule in `policies/detection-rules.yaml` shape: id, version, signal, window, threshold, evidence fields, mode (`observe` default), action ref, exceptions.
2. Prefer behavioral signals: failed-login spread across many accounts per IP, many accounts per fingerprint, sequential ID walking, 404 bursts, honeypot field/route hits, impossible request cadence.
3. User-Agent, geography and opaque scores are **supporting** signals only; never sole basis for blocking.
4. Run in `observe`, replay fixtures and recorded logs, compute false-positive list, then ask the user to promote to `alert`/`rate_limit`/`temp_block`.
5. Every decision emits a `security_decision` event (rule id+version, evidence, action, scope, expiry, idempotency key).

## 6. Security constraints
No LLM output as enforcement authority. Respect shared-IP environments and approved infrastructure exceptions. Blocks are temporary, scoped and reversible; broad or irreversible actions need human approval.

## 7. Implementation requirements
Deterministic evaluator in app code (pure function over events → decision), idempotent via key `rule_id:subject:window_start`, state in Redis/DB with TTL.

## 8. Test requirements
Attack fixtures (stuffing, enumeration, scanner) trigger; benign fixtures (shared NAT, health checks, search engines allowlisted by verified rDNS) do not; duplicate event → one decision; expiry removes block; evaluator failure → fail-open + health event.

## 9. Failure handling
Unknown/ambiguous evidence → `observe` or `manual_review`, never block.

## 10. Completion criteria
Rules validate against schema; fixtures pass; observe-only default confirmed; promotion criteria documented.

## 11. Required report format
```
Rules (id@version, mode) | Signals | Exceptions | Fixture results (TP/FP) | Promotion criteria | Unverified
```
