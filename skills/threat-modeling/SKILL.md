---
name: threat-modeling
description: "Build a lightweight STRIDE threat model for a feature or system: assets, trust boundaries, data flows, ranked threats, mitigations mapped to skills. Use before designing or approving security controls."
metadata:
  version: "0.1.0"
  category: design
---
# threat-modeling

## 1. Purpose
Turn an architecture into a ranked, testable list of threats and mitigations.

## 2. When to invoke
New feature touching auth, money, personal data, uploads, third-party callbacks; before the plan stage of any implementation.

## 3. Preconditions
Audit output (security-audit) or equivalent architecture knowledge; user has named the assets that matter.

## 4. Required discovery steps
Identify assets, actors (anonymous, user, admin, service, tenant), entry points, data stores, external systems, trust boundaries.

## 5. Detailed workflow
1. Draw data flows as a text table: source → destination | data | boundary crossed | protocol.
2. For each flow and each store apply STRIDE (Spoofing, Tampering, Repudiation, Information disclosure, DoS, Elevation).
3. Add abuse cases: credential stuffing, OTP brute force, enumeration, scraping, webhook replay, tenant hopping.
4. Score: likelihood 1-3 × impact 1-3. Keep threats ≥4 for mitigation planning.
5. Map each threat to a mitigation and the skill that implements it, and to an observable signal (event type from `contracts/`).
6. Record assumptions and accepted risks with owner.

## 6. Security constraints
No real secrets/data in the model. Accepted risks need explicit user sign-off.

## 7. Implementation requirements
Save as `docs/security/threat-model-<feature>.md` in the application repo (project scope) using the report format.

## 8. Test requirements
Each mitigated threat has at least one named test (or detection rule + simulated attack fixture).

## 9. Failure handling
Missing information → list as assumption with "needs confirmation"; never invent components.

## 10. Completion criteria
All flows crossing a trust boundary analysed; every threat scored ≥4 has mitigation, skill, signal, and test name.

## 11. Required report format
```
Assets | Actors | Trust boundaries
Data-flow table
Threats: ID | STRIDE | Description | L | I | Score | Mitigation | Skill | Signal | Test
Assumptions / Accepted risks (owner)
```
