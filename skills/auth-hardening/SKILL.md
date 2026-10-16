---
name: auth-hardening
description: "Harden authentication, sessions and authorization (login, password reset, OTP/MFA, tokens, policies/guards, object-level access) in Laravel or NestJS using native mechanisms. Use for login/session/token/permission weaknesses."
metadata:
  version: "0.1.0"
  category: implementation
---
# auth-hardening

## 1. Purpose
Make identity proof, session lifecycle and authorization checks correct, uniform and testable.

## 2. When to invoke
Audit found authn/authz gaps; adding roles, tenants, OTP, API tokens, or admin areas.

## 3. Preconditions
Approved plan; framework detected; auth mechanism known; test suite runnable locally.

## 4. Required discovery steps
Locate login/register/reset/OTP flows, token issuance, session config, middleware/guards, policies/gates, role model, tenant scoping.

## 5. Detailed workflow
1. Authentication: argon2id/bcrypt, constant-time compare, uniform error messages (no user enumeration), throttled login + reset + OTP verify, session ID regeneration on login/privilege change, logout invalidates server-side.
2. Tokens: short-lived access tokens, rotating refresh tokens with reuse detection, hashed storage of refresh/API tokens, revocation endpoint, no tokens in URLs/logs.
3. OTP: ≥6 digits, single-use, expiry ≤10 min, attempt cap per identifier AND per IP, resend cooldown, hashed at rest.
4. Authorization: central policy per resource (Laravel Policies/Gates; Nest Guards + ability checks). Deny by default. Every controller action authorizes the *object*, not just the role.
5. Tenant isolation: global scope / repository filter by tenant; tests prove cross-tenant access returns 403/404.
6. Emit security + audit events (login success/failure, lockout, token revoked, permission denied) per `contracts/`.

## 6. Security constraints
Do not weaken existing checks to make tests pass. Do not log credentials/OTP/tokens. Do not introduce custom crypto. Account lock must be controlled (temporary, notifying, reversible) — see `policies/response-actions.yaml`.

## 7. Implementation requirements
Use framework-native pieces (Laravel: middleware, `Gate::authorize`, `RateLimiter`, Sanctum/Fortify; Nest: Guards, `@nestjs/passport`/JWT, `@nestjs/throttler`). Config via env, no hard-coded secrets.

## 8. Test requirements
Feature tests: wrong password ×N throttled; enumeration-safe responses; session fixation; expired/reused refresh token rejected; IDOR across users and tenants; admin route as non-admin = 403; OTP reuse/expiry/attempt cap.

## 9. Failure handling
If existing flows cannot be changed without breaking clients, propose a versioned migration with dual-support window; do not silently break login.

## 10. Completion criteria
All listed tests green; every route has an explicit authz decision recorded in the coverage matrix; no new High finding in re-audit.

## 11. Required report format
```
Changes (file:line) | Controls added | Tests (name → result) | Events emitted | Residual risks | Unverified
```
