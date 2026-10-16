---
name: audit-trail
description: "Implement a tamper-evident, redacted audit trail for security-relevant domain actions (who did what to which target, when, outcome) in Laravel or NestJS, with retention and access control. Use for compliance and forensics needs."
metadata:
  version: "0.1.0"
  category: implementation
---
# audit-trail

## 1. Purpose
Record durable, queryable, minimal audit events for privileged and sensitive actions.

## 2. When to invoke
Role/permission changes, money movement, data export, account lock/unlock, security-rule changes, admin actions, automated response decisions.

## 3. Preconditions
Event catalogue agreed (which actions are audited); storage with append-only discipline.

## 4. Required discovery steps
Find existing activity logs, domain events, admin actions; identify actor and target models and tenant key.

## 5. Detailed workflow
1. Define audit event types per `contracts/audit-event.schema.json` (actor, action, target, outcome, request_id, changes summary).
2. Hook at the domain layer (Laravel model events/observers/domain events; Nest service methods/interceptors) — not at controllers only.
3. Store `changes` as field-name lists or redacted diffs; never raw sensitive values.
4. Make append-only: no UPDATE/DELETE grants for the app role on the audit table; optional hash chain (`prev_hash`, `hash`).
5. Write in the same transaction as the action (or outbox) so audited actions cannot happen unaudited.
6. Retention + access: only security/admin roles read; retention from `policies/defaults.yaml`.

## 6. Security constraints
Audit data may itself be sensitive: redact, restrict access, never expose via public API.

## 7. Implementation requirements
Single `AuditService`/`AuditLogger` entry point; queue only if outbox guarantees delivery.

## 8. Test requirements
Action produces exactly one valid event; failed action produces `outcome=failure` event; secrets not stored; app role cannot update/delete; hash chain verification detects tampering (if enabled).

## 9. Failure handling
Audit write failure on a critical action → abort the action (fail-closed) unless the action is marked best-effort in config.

## 10. Completion criteria
Catalogued actions all covered by passing tests; schema validation in tests.

## 11. Required report format
```
Audited actions | Event type | Storage & immutability | Redaction | Tests → results | Retention | Unverified
```
