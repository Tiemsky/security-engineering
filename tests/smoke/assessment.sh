#!/usr/bin/env bash
# Behavioural consistency of the environment-assessment protocol in REAL sessions: same scenario, same expected ENV/GATE in every tool.
# Usage: assessment.sh <claude|opencode|antigravity> <evidence_dir> [--with-model <provider/model>]   (opencode needs --with-model)
# Cost: 4 short model calls per tool. Fictional fixtures only; no network tool is available to the agents. A failed model call is reported NOT VERIFIED, never PASS.
# The gate (scripts/assessment-gate.py) is the reference answer; the model's answer is compared with it, not trusted.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"; TOOL="$1"; EV="$(mkdir -p "$2" && cd "$2" && pwd)"; MODEL="${4:-}"; H="$ROOT/tests/smoke/assessment_prep.py"
W="$(mktemp -d)"; cp -r "$ROOT/tests/fixtures/smoke-project/." "$W"; cd "$W"; git init -q; git add -A; git -c user.email=t@t -c user.name=t commit -qm fixture
"$ROOT/scripts/install.sh" --mode project --project-dir "$W" --tools "$TOOL" --vendor-skills | tail -1
verdict() { # name jsonl
  read -r e g < <(python3 "$H" parse "$2"); read -r xe xg < <(python3 "$H" expect "$1")
  if [ "$e" = NONE ] || [ "$g" = NONE ]; then echo "$TOOL $1: NOT VERIFIED (no ENV/GATE answer: model call failed or format ignored)"
  elif [ "$e" = "$xe" ] && [ "$g" = "$xg" ]; then echo "$TOOL $1: PASS (ENV=$e GATE=$g as the deterministic gate)"
  else echo "$TOOL $1: FAIL (got ENV=$e GATE=$g; gate says ENV=$xe GATE=$xg)"; fi; }
for n in $(python3 "$H" names); do
  P="$(python3 "$H" prep "$W" "$n")"; OUT="$EV/assessment-$TOOL-$n.jsonl"
  case "$TOOL" in
    claude) claude -p "$P" --agent security-orchestrator --model "${CLAUDE_MODEL:-haiku}" --max-budget-usd 0.40 --no-session-persistence --output-format stream-json --verbose > "$OUT" 2>/dev/null || true;;
    antigravity) agy -p "$P" --agent security-orchestrator --effort low --print-timeout 250s --output-format stream-json > "$OUT" 2>/dev/null || true;;
    opencode) [ -n "$MODEL" ] || { echo "opencode needs --with-model <provider/model>"; exit 2; }
      docker build -q -t se-opencode-smoke -f "$ROOT/tests/integration/docker/Dockerfile.opencode" "$ROOT/tests/integration/docker" >/dev/null
      docker run --rm -v "$W:/work" -v "$ROOT:/repo:ro" -w /work se-opencode-smoke opencode run --agent security-orchestrator --model "$MODEL" --format json "$P" > "$OUT" 2>"$OUT.err" || true;;
    *) echo "unknown tool $TOOL"; exit 2;;
  esac
  verdict "$n" "$OUT"
done
git status --short | grep -v '^??' && echo "WARNING: tracked files changed" || echo "$TOOL: source tree unchanged"
