# Pilot protocol — read-only audit of any application

A repeatable procedure to audit any Laravel, NestJS or other application with `security-auditor`, without touching the source repository and without showing secrets to a model. Pilot A (leyinvest-api) was run by hand; this protocol turns it into steps that work for any project. Scope: **static, code-only**. Staging and production assessments need the gate and an external tool (see [USER-GUIDE.md](USER-GUIDE.md) §6b); nothing here contacts a target.

Labels: **TESTED** (automated test in `tests/pilot`) · **EXECUTED** (run for real in pilot A) · **NOT-VERIFIED**.

## 1. Build the audit copy — TESTED
```bash
scripts/audit-copy.sh --repo ~/Apps/my-app --out /tmp/my-app-audit --dry-run   # lists name-based exclusions, writes nothing
scripts/audit-copy.sh --repo ~/Apps/my-app --out /tmp/my-app-audit             # add --ref <rev> to pin a commit
```
- Copies the **committed** state through a temporary index (uncommitted and untracked files are left out; the source repository is never written to and its `git status` is compared before/after).
- Uses the tracked-file list, so `export-ignore` cannot drop CI files (pilot defect H1).
- Removes secret-bearing files by name (`.env*` except examples, keys, keystores, `.npmrc`, tfstate…) and by content shape (private keys, AWS/GitHub/Slack/Google/Brevo/Stripe/Anthropic key shapes), and removes symlinks. Every exclusion is listed with its reason (never a value) in `AUDIT-COPY.txt`.
- **Exit 5** = secret-bearing files are tracked in git. The copy is still produced. Check whether they are real and rotate them; consider purging the history. This is a finding for the owner, whatever the agent later reports.
- Limit: shape matching is heuristic. A secret with an unusual shape can pass. Treat the copy as a reduction of exposure, not a guarantee.

## 2. Install the toolkit in the copy and define the scope — TESTED (installer), EXECUTED (pilot A)
```bash
scripts/install.sh --mode project --project-dir /tmp/my-app-audit --vendor-skills
cp adapters/project/assessment-scope.yaml.template /tmp/my-app-audit/.security-engineering/assessment-scope.yaml
python3 scripts/assessment-gate.py classify /tmp/my-app-audit/.security-engineering/assessment-scope.yaml
```
Fill the scope with verifiable evidence only (a hostname is not evidence). With no authorization recorded, the mode is `code-only`. Set `framework` in `.security-engineering/config.yaml`.

## 3. Run the audit — EXECUTED (pilot A, Claude Code)
Start from `adapters/project/audit-prompt.txt.template`: replace `{{NAME}}`, `{{FRAMEWORK}}` and `{{FRAMEWORK_FOCUS}}` (Laravel: FormRequests, Policies/Gates, middleware, Eloquent `$fillable`/`$hidden`, Sanctum, queues; NestJS: Guards, `ValidationPipe`, DTOs, interceptors, Prisma raw queries, throttler). Save the prompt next to the report.
```bash
cd /tmp/my-app-audit
claude -p "$(cat ../prompt.txt)" --agent security-auditor --model sonnet --max-budget-usd 3 --no-session-persistence --output-format stream-json --verbose < /dev/null > ../audit.jsonl
```
Record in a `RUN.md` beside the outputs: toolkit commit, source commit (from `AUDIT-COPY.txt`), tool and model versions, cost, duration, tool calls. OpenCode and Antigravity use their own syntax ([COMMAND-REFERENCE.md](COMMAND-REFERENCE.md) §2–3; for those tools the audit prompt run is NOT-VERIFIED).

## 4. Validate the report — TESTED
```bash
scripts/extract-report-json.py report.md matrix.json
python3 scripts/assessment-gate.py validate-report matrix.json      # structure and cross-field rules, NOT truth
```

## 5. Verify findings independently
`valid` does not mean the findings are right. For each Critical and High finding, read the cited code yourself (or have a different session do it) and fill a table: finding, check performed, result (`confirmed` / `false positive` / `unverified`). For Medium and Low, sample at least a third. Record false positives and the cause (agent error versus harness error). Without this table the audit is a lead list, not a verified result.

## 6. Prove the source was not touched
`audit-copy.sh` already compares `git status` before and after. For a stronger check, create a marker file before the run and confirm that no file outside `.git` is newer than it afterwards. The auditor's tools (`Read`, `Grep`, `Glob`) are visible in the first `system/init` event of `audit.jsonl`.

## 7. Repeat
One run proves little. Repeat three times with the same commit and prompt and compare: findings found by all runs, by some, by one. Report the spread.

## 8. Keep the results private
`report.md` lists vulnerabilities: store it outside the toolkit repository, and put only a summary (counts, verification table, defects of the harness) in `docs/`.
