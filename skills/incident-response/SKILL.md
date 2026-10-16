---
name: incident-response
description: "Prepare and run security incident response: detection-to-containment runbooks, safe automated actions with human approval gates, evidence preservation, rollback and post-incident review. Use for active incidents or runbook design."
metadata:
  version: "0.1.0"
  category: operations
---
# incident-response

## 1. Purpose
Contain and understand incidents quickly while keeping every action evidenced, scoped and reversible.

## 2. When to invoke
Suspected breach/abuse, alert triggers, designing response automation, post-incident review.

## 3. Preconditions
Access to logs/events (read-only first). Named human decision-maker for approvals.

## 4. Required discovery steps
Timeline from `http_access`/`security_event`/`audit_event`; affected actors, tenants, endpoints; current mode of detection rules; active blocks.

## 5. Detailed workflow
1. Triage: severity, scope, ongoing vs historical. 2. Preserve evidence (export relevant events, do not delete).
3. Contain using the least-broad action from `policies/response-actions.yaml` (rate limit → temp IP block → session revocation → account lock).
4. Actions that are destructive, irreversible, broad-impact or weakly evidenced require explicit human approval; record approver.
5. Eradicate/recover: rotate exposed secrets (through the owner, never paste secrets), patch, revoke sessions/tokens.
6. Review: root cause, detection gap, new/updated rule (starts in observe), new tests.

## 6. Security constraints
No retaliation, no scanning third parties, no production tests. Do not echo secrets in reports.

## 7. Implementation requirements
Runbooks in `docs/security/runbooks/` of the app; response actions implemented as idempotent commands with expiry and rollback.

## 8. Test requirements
Each action has tests: idempotent re-run, expiry/rollback, false-positive guard, failure path (action fails → recorded as `failed`, no partial state).

## 9. Failure handling
If evidence is insufficient: escalate to `manual_review`; if an action fails, record outcome and stop automation for that rule.

## 10. Completion criteria
Timeline, containment decisions with approvals, rollback status and follow-up tasks documented.

## 11. Required report format
```
Timeline (UTC) | Impact | Actions: id, scope, expiry, approver, outcome | Evidence refs | Root cause | Follow-ups | Unverified
```
