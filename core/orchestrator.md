# Orchestrator specification
Pipeline: **Scope → Discover → Model → Plan → Implement → Validate → Review → Report.**

| Stage | Agent | Skills | Gate to continue |
|---|---|---|---|
| Scope | orchestrator | environment-assessment | environment profile + authorized scope recorded; mode chosen (`code-only` if ambiguous) |
| Discover | architect/auditor | security-audit, framework-adapter-development | framework, auth model, entry points identified |
| Model | architect | threat-modeling | threats ranked, assumptions listed |
| Plan | architect | per-control skill | user approves plan, observe-only default confirmed |
| Implement | implementer | auth-hardening, api-security, rate-limiting, request-observability, bot-detection, audit-trail, devsecops | tests written first/with change |
| Validate | implementer/orchestrator | security-validation | all tests green, real output captured |
| Review | reviewer (fresh context) | security-validation | no open High/Critical |
| Respond | architect | incident-response | runbook + human-approval points |

Rules: select the minimum skills needed; track dependencies (e.g. rate-limiting needs request-observability events; bot-detection needs rate-limiting
and audit-trail); never skip Review; stop and ask when a gate fails twice. Fallback when no independent agent exists: run the Reviewer
checklist in a new session/context and say so in the report.
