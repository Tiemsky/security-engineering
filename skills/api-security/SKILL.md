---
name: api-security
description: "Secure HTTP APIs: input validation, mass assignment, output filtering, CORS, security headers, file uploads, SSRF, webhooks, pagination limits and error handling in Laravel or NestJS. Use for endpoint-level hardening."
metadata:
  version: "0.1.0"
  category: implementation
---
# api-security

## 1. Purpose
Ensure every endpoint validates input, limits resources, exposes only intended fields and fails safely.

## 2. When to invoke
New/changed endpoints; audit findings on validation, CORS, headers, uploads, webhooks, SSRF.

## 3. Preconditions
Endpoint inventory (from security-audit); approved plan.

## 4. Required discovery steps
List routes with method, auth, request schema, response shape; find upload, webhook, outbound-HTTP and redirect code.

## 5. Detailed workflow
1. Validation: Laravel FormRequest / Nest DTO + `ValidationPipe({whitelist:true, forbidNonWhitelisted:true, transform:true})`; reject unknown fields.
2. Output: API Resources / serializers with explicit field allowlists; never return models/entities raw (no password hashes, tokens, internal IDs beyond need).
3. Limits: max body size, pagination max (`per_page ≤ 100`), query depth/complexity for GraphQL, upload size.
4. CORS: explicit origin allowlist; never `*` with credentials. Headers: HSTS, `X-Content-Type-Options`, frame protections, CSP where HTML is served, `Cache-Control: no-store` on sensitive responses.
5. Uploads: validate content type by sniffing, random server names, outside web root, AV hook optional, no execution.
6. SSRF: outbound requests from user URLs → scheme allowlist, DNS resolve then block private/loopback/link-local/metadata ranges, no redirects or re-validate.
7. Webhooks: HMAC signature over raw body, timestamp tolerance, idempotency key store.
8. Errors: generic messages + correlation ID; no stack traces; consistent 401/403/404 semantics.

## 6. Security constraints
No wildcard CORS with credentials; no disabling TLS verification; no raw SQL with interpolation; keep error bodies free of internals.

## 7. Implementation requirements
Native validators/middleware only; shared helper for SSRF guard and webhook verifier placed once, reused.

## 8. Test requirements
Unknown-field rejected; oversized body/page size capped; response omits sensitive fields; CORS from disallowed origin; SSRF payloads (`http://169.254.169.254`, `http://[::1]`, `file://`, redirect to private) blocked; webhook with bad signature/replay rejected.

## 9. Failure handling
If a legacy client depends on loose behavior, add deprecation window + metric event instead of silently breaking.

## 10. Completion criteria
Each endpoint in the matrix has validation, output allowlist, limits; negative tests green.

## 11. Required report format
```
Endpoint matrix (before/after) | Changes | Negative tests → results | Compatibility notes | Unverified
```
