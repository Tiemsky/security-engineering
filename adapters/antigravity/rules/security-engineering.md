---
trigger: model_decision
description: Security engineering workflow. Apply when the task involves authentication, authorization, sessions, API hardening, rate limiting, bot detection, audit logging, security reviews, incident response or CI/CD security.
---
# Security engineering workflow

Skills are installed (names: security-audit, threat-modeling, auth-hardening, api-security, request-observability, bot-detection, rate-limiting, audit-trail, incident-response, devsecops, security-validation, framework-adapter-development). Read the matching skill's SKILL.md before acting.

Pipeline: Discover → Model → Plan → Implement → Validate → Review → Report. Stages: security-audit → threat-modeling → (plan, user approval) → per-control skill → security-validation (fresh context).

Roles (custom subagents `security-architect`, `security-implementer`, `security-auditor`, `security-reviewer` if available; otherwise play the roles sequentially and say so):
- Auditor/Architect/Reviewer: read-only. Implementer: only after the user approves the plan.

Hard rules:
- Never print, store or commit secrets, tokens, OTPs, cookies or Authorization headers.
- Detection/response rules start in `observe`. Blocking requires explicit user approval and a rule with evidence, scope, expiry, rollback. No LLM output is an enforcement authority.
- Never widen permissions or run against production.
- Final report separates Implemented / Tested / Unverified.
