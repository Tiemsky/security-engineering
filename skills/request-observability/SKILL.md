---
name: request-observability
description: "Instrument the HTTP request lifecycle to emit structured, redacted HTTP access and security events with request/trace correlation (IPv4/IPv6, trusted proxies). Foundation for detection, rate limiting and audit."
metadata:
  version: "0.1.0"
  category: implementation
---
# request-observability

## 1. Purpose
Produce reliable `http_access` and `security_event` records conforming to `contracts/`, without leaking sensitive data or hurting latency.

## 2. When to invoke
Before bot-detection, rate-limiting or incident-response work; when logs are unstructured or lack correlation.

## 3. Preconditions
Know the deployment topology (reverse proxy/CDN) to configure trusted proxies correctly.

## 4. Required discovery steps
Find existing logging, middleware order, trusted proxy config, queue infrastructure, log sink.

## 5. Detailed workflow
1. Generate/propagate `request_id` (accept inbound only from trusted proxy) and W3C `traceparent` correlation.
2. Resolve client IP only via trusted-proxy rules (never raw `X-Forwarded-For`); support IPv4/IPv6; store normalized text form.
3. Capture on response/terminate: method, route *template* (not raw URL with IDs), status, duration, bytes, user-agent (truncated), actor ref (hashed/opaque id), tenant.
4. Apply `policies/redaction.yaml` to headers, query strings, bodies (default: no body capture).
5. Emit asynchronously (queue/buffer); failure of logging must never fail the request.
6. Emit `security_event` for authn/authz failures, validation floods, signature failures.

## 6. Security constraints
Never record passwords, OTPs, tokens, cookies, Authorization headers, API secrets, payment credentials, full sensitive bodies. Minimize PII; hash identifiers where correlation suffices.

## 7. Implementation requirements
Laravel: middleware + `terminate()` + queued job. Nest: middleware (id) + interceptor (timing) + exception filter (errors). See `adapters-runtime/`.

## 8. Test requirements
Schema-valid events; redaction test with seeded secrets; spoofed `X-Forwarded-For` from untrusted peer ignored; IPv6 handled; logger exception does not change response; route template used.

## 9. Failure handling
Sink down → drop with counter + `system_health` event, never block. Over-capacity → sample non-security events only.

## 10. Completion criteria
Events validate against schemas in the real request path of the app (integration test, not unit-only); redaction test green.

## 11. Required report format
```
Middleware order | Fields captured | Redaction rules applied | Sample event (redacted) | Tests → results | Perf note | Unverified
```
