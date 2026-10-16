---
name: rate-limiting
description: "Implement layered rate limiting and throttling (per IP, per account, per route, per tenant) with correct client identification, 429 semantics and safe failure, using native Laravel RateLimiter or NestJS Throttler. Use for brute-force and resource-abuse protection."
metadata:
  version: "0.1.0"
  category: implementation
---
# rate-limiting

## 1. Purpose
Bound abuse and resource consumption without punishing legitimate shared-IP users.

## 2. When to invoke
Login/OTP/reset/signup endpoints, expensive queries, public APIs, after audit flags missing throttles.

## 3. Preconditions
Trusted proxy config correct (see request-observability); shared store (Redis/DB) available for multi-instance deployments.

## 4. Required discovery steps
List sensitive routes and their legitimate peak rates; find existing throttles; identify NAT/carrier/office clients.

## 5. Detailed workflow
1. Define limiter keys per route class: `login: ip + normalized identifier`, `otp-verify: identifier` (+ ip), `api: token/user`, `anon: ip` (IPv6 → /64 prefix).
2. Use two dimensions on credential endpoints so one IP cannot hammer many accounts nor many IPs one account.
3. Return `429` + `Retry-After`; same response shape regardless of whether the account exists.
4. Progressive backoff for repeated violations only through `policies/response-actions.yaml` actions with expiry.
5. Emit `security_event` on limit hit (observe counters first when rolling out).
6. Fail-open on store outage for general API, fail-closed (conservative) for OTP/login verification with health event.

## 6. Security constraints
Never key solely on spoofable headers. No permanent bans. Exempt only approved infrastructure (health checks) via config, with audit.

## 7. Implementation requirements
Laravel `RateLimiter::for()` + `throttle:` middleware; Nest `ThrottlerModule` with custom `getTracker`, Redis storage. Limits in config/env, not code.

## 8. Test requirements
N+1th request gets 429 with Retry-After; limiter reset after window; per-account key independent of IP; IPv6 /64 aggregation; store down behaviour per route class; shared-IP fixture not blocked by per-account limits.

## 9. Failure handling
If limits break legitimate flows in staging fixtures, loosen via config and document; do not remove the limiter.

## 10. Completion criteria
Every sensitive route has a tested limiter; behaviour on store failure documented and tested.

## 11. Required report format
```
Route class | key | limit/window | on-store-failure | Tests → results | Exceptions | Unverified
```
