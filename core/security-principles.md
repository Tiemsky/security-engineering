# Security principles
1. **Evidence over assertion** — every finding cites file:line or a reproducible request; no evidence → "unverified".
2. **Least privilege** — for agents, services, tokens and automated actions.
3. **Deny by default** at authorization boundaries; object-level checks on every resource access (IDOR).
4. **Defense in depth, fail safe** — a failing detector must not block legitimate traffic; a failing authz check must deny.
5. **Minimize data** — never log passwords, OTPs, raw tokens, cookies, Authorization headers, API secrets, payment credentials, full sensitive bodies.
6. **Deterministic enforcement** — blocking decisions come from versioned rules with evidence, scope, expiry; never from free-form LLM output, UA, geo or opaque score alone.
7. **Reversible by default** — every automatic action expires or can be rolled back; destructive/broad actions need human approval.
8. **Observe first** — new detections start in `observe`, are promoted after measured false-positive review.
9. **Respect framework conventions** — use native middleware/guards/policies, not parallel mechanisms.
10. **Test what you claim** — static verification is labelled static; never claim a tool loaded an agent unless it was run.
