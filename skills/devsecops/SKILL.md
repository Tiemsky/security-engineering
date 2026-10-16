---
name: devsecops
description: "Integrate security checks into CI/CD and delivery: dependency audit, secret scanning, SAST hooks, container hardening, pinned actions, least-privilege pipelines and deployment events. Use when setting up or reviewing pipelines."
metadata:
  version: "0.1.0"
  category: operations
---
# devsecops

## 1. Purpose
Make security regressions fail the build and make deployments traceable.

## 2. When to invoke
New repo, new pipeline, audit findings on CI/CD/Docker, release hardening.

## 3. Preconditions
CI provider known; permission to add workflow files.

## 4. Required discovery steps
Read existing CI files, Dockerfiles, compose, lockfiles, `.gitignore` (is `.env` ignored?), branch protections if visible.

## 5. Detailed workflow
1. Dependency audit job (`composer audit`, `npm audit --omit=dev`) failing on High+.
2. Secret scanning (pre-commit + CI), baseline file for reviewed false positives.
3. Pin third-party actions by commit SHA or exact version; least-privilege `permissions:` (default `contents: read`).
4. Containers: non-root user, minimal base, no secrets in layers/build args, read-only FS where feasible, no `--privileged`.
5. Run the security test suite and schema/policy validation on every PR.
6. Emit a `deployment_event` (version, commit, actor, result) at deploy.

## 6. Security constraints
Never print secrets in CI logs; no `pull_request_target` with untrusted checkout; deploy credentials only in the CI secret store.

## 7. Implementation requirements
Minimal, readable workflow files; no new runtime dependency solely for CI.

## 8. Test requirements
CI run on a branch demonstrates failure on a seeded vulnerable dependency/secret fixture (in a throwaway branch/fixture) and success on clean.

## 9. Failure handling
Flaky scanner → pin version, add reviewed baseline entry with expiry; do not disable the job.

## 10. Completion criteria
Pipelines green on clean main; seeded failure detected; permissions minimal.

## 11. Required report format
```
Jobs added/changed | Permissions | Pins | Container changes | Evidence of failing-then-passing run | Unverified
```
