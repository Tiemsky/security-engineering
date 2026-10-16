# Audit checklist (condensed)
- BOLA/IDOR: every `find($id)` / `findOrFail` / repository lookup scoped by owner/tenant or authorized by policy/guard.
- Mass assignment: Laravel `$fillable`/`$guarded` not `[]`; Nest DTOs use `whitelist: true, forbidNonWhitelisted: true`.
- Auth: password hashing (argon2id/bcrypt), lockout/throttle, session regeneration on login, token expiry/rotation, MFA for admin.
- Transport/headers: HSTS, secure+httponly+samesite cookies, CORS not `*` with credentials, CSP.
- Uploads: type by content, size cap, stored outside web root, random names.
- SSRF: outbound fetch with user URL → allowlist + block private ranges.
- Webhooks: signature verification + replay window + idempotency key.
- Logging: no secrets/PII in logs; security events structured (see `contracts/`).
- Debug: `APP_DEBUG=false`, no stack traces to clients, no exposed admin/telescope/swagger in prod.
