---
name: security-validation
description: "Independently validate security changes: run tests, replay attack and benign fixtures, check authorization boundaries, least privilege, redaction and idempotency, and report implemented vs tested vs unverified. Use as the review gate before declaring work done."
metadata:
  version: "0.1.0"
  category: assurance
---
# security-validation

## 1. Purpose
Provide an independent, evidence-based verdict on a security change.

## 2. When to invoke
After every implementation; before merge/release; when claims of "secure" need proof.

## 3. Preconditions
Diff or commit range; ability to run the test suite locally; reviewer context separate from the implementer when possible.

## 4. Required discovery steps
Read the plan, the diff, the tests, the active policies; identify changed trust boundaries.

## 5. Detailed workflow
1. Run the full relevant test suites; capture exact commands and results.
2. Authorization review: for each changed/new route, verify authn, authz, object-level and tenant checks exist and are tested negatively.
3. Redaction review: grep emitted events/logs in tests for seeded secrets.
4. Policy review: modes (`observe` default), scopes, expiry, idempotency, rollback present; false-positive fixtures present.
5. Regression review: behavior of existing flows unchanged unless planned.
6. Try to break it: replay attack fixtures against the test app only.
7. Classify findings; any High/Critical blocks completion.

## 6. Security constraints
Read-only on source (reports only). Tests run against local/ephemeral environments, never production.

## 7. Implementation requirements
None; may add missing tests only if the user asks the implementer.

## 8. Test requirements
Meta: the validation itself lists which checks were executed vs only statically reviewed.

## 9. Failure handling
Tests cannot run → report "not executed" with reason; never infer pass.

## 10. Completion criteria
Verdict (Approve / Approve with conditions / Reject) with evidence; table separating Implemented / Tested / Unverified.

## 11. Required report format
```
Verdict | Commands executed + results | Findings (severity, evidence) | Authorization matrix | Implemented / Tested / Unverified
```
