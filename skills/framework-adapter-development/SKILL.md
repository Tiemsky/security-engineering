---
name: framework-adapter-development
description: "Create or extend a framework runtime adapter (Laravel, NestJS, or a new one) that implements the shared security contracts using native framework mechanisms and is wired into the real request path. Use when supporting a new framework or porting a control."
metadata:
  version: "0.1.0"
  category: implementation
---
# framework-adapter-development

## 1. Purpose
Keep security semantics identical across frameworks while using each framework's idioms.

## 2. When to invoke
Adding a framework; adding a contract field; porting a control from one adapter to another.

## 3. Preconditions
Contracts (`contracts/`) and policies stable for the target version; framework version known.

## 4. Required discovery steps
Map framework equivalents: middleware, authz (policies/guards), error handling, rate limiter, queue, DI/service container, test harness.

## 5. Detailed workflow
1. Write a mapping table: contract field → where it is produced in the lifecycle.
2. Implement under `adapters-runtime/<framework>/` with native structure (do not mirror another framework's folders).
3. Provide an integration example that boots a real request path (sample app or test kernel).
4. Add the framework to `tests/integration/` with the shared fixtures; the same fixture must yield schema-valid events and identical decisions across frameworks.
5. Document install/wiring steps and version support range.

## 6. Security constraints
No disconnected runtime code; no framework-specific fields in shared contracts (put in `extensions` object).

## 7. Implementation requirements
Pure decision engine separated from I/O; adapters only translate request/response ↔ events and apply decisions.

## 8. Test requirements
Cross-framework contract test; redaction test; idempotency test; failure-mode (logger/store down) test.

## 9. Failure handling
Unsupported framework feature → document gap and fallback (e.g. no native challenge) rather than emulate unsafely.

## 10. Completion criteria
Mapping table complete; integration test executes in the framework's real runtime (or is explicitly reported as not executed).

## 11. Required report format
```
Framework/version | Mapping table | Files | Tests executed (runtime) vs static | Gaps/fallbacks | Unverified
```
