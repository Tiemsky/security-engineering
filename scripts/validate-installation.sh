#!/usr/bin/env bash
# STATIC verification of an installation (files, hashes, frontmatter, version pin). It does NOT prove a tool loaded the agents/skills.
# Usage: validate-installation.sh --mode global|project [--project-dir DIR]     Exit 1 on any failure.
set -uo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
MODE=""; PROJECT_DIR=""
while [ $# -gt 0 ]; do case "$1" in --mode) MODE="$2"; shift 2;; --project-dir) PROJECT_DIR="$2"; shift 2;; *) echo "unknown option $1" >&2; exit 2;; esac; done
[ "$MODE" = global ] || [ "$MODE" = project ] || { echo "--mode required" >&2; exit 2; }
resolve_paths; FAIL=0; CHECKED=0
bad() { echo "FAIL: $*"; FAIL=$((FAIL+1)); }
[ -f "$MANIFEST" ] || { bad "no manifest at $MANIFEST"; exit 1; }
ver="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1]))["version"])' "$MANIFEST")"
while IFS=$'\t' read -r f h; do
  CHECKED=$((CHECKED+1))
  [ -f "$f" ] || { bad "missing $f"; continue; }
  [ "$(sha "$f")" = "$h" ] || bad "modified since install: $f"
  case "$f" in
    */SKILL.md) d="$(basename "$(dirname "$f")")"; n="$(sed -n '2,10s/^name:[[:space:]]*//p' "$f" | head -1)"
      [ "$(head -1 "$f")" = "---" ] || bad "no frontmatter $f"; [ "$n" = "$d" ] || bad "skill name '$n' != dir '$d' ($f)";;
    */agents/*.md) [ "$(head -1 "$f")" = "---" ] || bad "no frontmatter $f";;
  esac
done < <(python3 -c 'import json,sys;[print(k+"\t"+v) for k,v in json.load(open(sys.argv[1]))["files"].items()]' "$MANIFEST")
if [ "$MODE" = project ]; then
  c="$ROOT_STATE/config.yaml"; [ -f "$c" ] || bad "missing $c"
  pin="$(sed -n 's/^security_engineering_version:[[:space:]]*"\{0,1\}\([0-9][0-9.]*\)"\{0,1\}.*/\1/p' "$c" 2>/dev/null | head -1)"
  [ "$pin" = "$ver" ] || bad "pin '$pin' != installed version '$ver'"
  for b in $(python3 -c 'import json,sys;print(" ".join(json.load(open(sys.argv[1])).get("blocks",[])))' "$MANIFEST"); do grep -qF "security-engineering:begin" "$b" || bad "managed block missing in $b"; done
fi
echo "checked $CHECKED file(s), version $ver, static verification only (no tool was launched)"
[ $FAIL -eq 0 ] && echo "OK" || { echo "$FAIL failure(s)"; exit 1; }
