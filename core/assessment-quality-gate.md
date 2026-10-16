# Assessment quality gate
An assessment is only as good as its environment identification, scope control, evidence and safety. Audit **coverage** is not the same as the **actual security** of the system: no agent can certify an application invulnerable. The gate evaluates five capacities; each says what is checked automatically and what still needs a human.

| # | Capacity | Passing means | Automated check | Human / real-session check |
|---|---|---|---|---|
| 1 | **Environment Detection** | environment, confidence, evidence and ambiguities recorded; hostnames/URLs and bare declarations never decide; conflicts resolve to `unknown` | `tests/assessment` — 13 scenarios (`tests/fixtures/assessment/scenarios.json`), classification invariants | `tests/smoke/assessment.sh`: each tool must reach the same decision on the same scenario |
| 2 | **Assessment Coverage** | the matrix contains every topic of the mode (`core/assessment-coverage.yaml`) — as a result or an honest `NOT_TESTED` with reason | `validate-report` coverage rule; tests remove each topic and expect a failure | reviewer judges whether topics are relevant for the application |
| 3 | **Evidence Quality** | PASS has evidence and non-low confidence; a code-only/local audit cannot PASS operational or dynamic controls; FAIL has severity, remediation, retest; summary agrees with matrix; no "completely secure" claim | `validate-report` rules, one mutation test per rule | reviewer samples evidence for accuracy (a validator cannot judge truth) |
| 4 | **Operational Safety** | no active step without gate `allow`; exploitation and enforcement never agent-initiated; production heavy activity needs a specific unexpired exception; rate caps (local 200 / staging 50 / production 5 rps) | every gate rule exercised by ≥1 scenario (guard test); invariants over all scenarios | real sessions: the agent must refuse or ask (`needs_confirmation` / `deny`) |
| 5 | **Continuous Improvement** | each gap found becomes a regression test and is re-reviewed by an independent agent | guard test: a gate rule without a scenario fails the suite; `tests/run_all.sh` | the improvement cycle below |

## Improvement cycle (evaluator → optimizer → independent review)
1. **Evaluate** a finished assessment against the five capacities (above); list the unmet criteria.
2. **Optimize**: change the skill, agent text, coverage topics or gate — one cause at a time — and add a test or scenario that fails before the change.
3. **Regress**: `tests/run_all.sh` must stay green; adapters regenerated and in sync.
4. **Independent review**: a fresh `security-reviewer` session checks the diff (it did not write it). No self-approval.
5. Record the result in `docs/validation-*.md` as executed or not executed.

## What stays outside the LLM
Classification, authorization decisions, rate caps and report validation are code (`scripts/assessment-gate.py`), deterministic and tested. The LLM gathers evidence, explains, proposes rules and remediation; it does not authorize active tests, production enforcement, or override a `deny`. Runtime policies remain observe-only (`policies/defaults.yaml`).
