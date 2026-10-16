#!/usr/bin/env bash
# Removes ONLY files recorded in the manifest and still unmodified; keeps anything the user changed.
# Usage: uninstall.sh --mode global|project [--project-dir DIR] [--dry-run] [--restore-backups]
set -euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
MODE=""; PROJECT_DIR=""; DRY=0; RESTORE=0
while [ $# -gt 0 ]; do case "$1" in --mode) MODE="$2"; shift 2;; --project-dir) PROJECT_DIR="$2"; shift 2;; --dry-run) DRY=1; shift;; --restore-backups) RESTORE=1; shift;; *) echo "unknown option $1" >&2; exit 2;; esac; done
[ "$MODE" = global ] || [ "$MODE" = project ] || { echo "--mode global|project required" >&2; exit 2; }
resolve_paths
[ -f "$MANIFEST" ] || { echo "nothing to uninstall (no manifest at $MANIFEST)"; exit 0; }
run() { echo "  $([ $DRY = 1 ] && echo '[dry-run] ')$*"; }
removed=0; kept=0
while IFS=$'\t' read -r f h; do
  [ -e "$f" ] || continue
  if [ "$(sha "$f")" = "$h" ]; then run "remove $f"; [ $DRY = 1 ] || { rm -f "$f"; rmdir -p "$(dirname "$f")" 2>/dev/null || true; }; removed=$((removed+1))
  else echo "  KEEP (modified since install) $f"; kept=$((kept+1)); fi
done < <(python3 -c 'import json,sys;[print(k+"\t"+v) for k,v in json.load(open(sys.argv[1]))["files"].items()]' "$MANIFEST")
for f in $(python3 -c 'import json,sys;print(" ".join(json.load(open(sys.argv[1])).get("blocks",[])))' "$MANIFEST"); do
  [ -f "$f" ] || continue; run "remove managed block from $f"
  [ $DRY = 1 ] || { awk 'BEGIN{s=0} $0=="<!-- security-engineering:begin -->"{s=1;next} $0=="<!-- security-engineering:end -->"{s=0;next} !s{print}' "$f" > "$f.new" && mv "$f.new" "$f"; [ -s "$f" ] && grep -q '[^[:space:]]' "$f" || rm -f "$f"; }
done
if [ "$MODE" = project ] && [ -f "$PROJECT_DIR/opencode.json" ]; then
  run "remove instructions entry from opencode.json"
  [ $DRY = 1 ] || python3 - "$PROJECT_DIR/opencode.json" <<'PY'
import json,sys
p=sys.argv[1]; d=json.load(open(p)); e=".security-engineering/PROJECT_RULES.md"
if e in d.get("instructions",[]): d["instructions"].remove(e)
if not d.get("instructions",True): d.pop("instructions")
json.dump(d,open(p,"w"),indent=2); open(p,"a").write("\n")
PY
fi
if [ $RESTORE = 1 ]; then
  for pair in $(python3 -c 'import json,sys;print(" ".join(k+"="+v for k,v in json.load(open(sys.argv[1])).get("backups",{}).items()))' "$MANIFEST"); do
    o="${pair%%=*}"; b="${pair#*=}"; [ -f "$b" ] && { run "restore $o from $b"; [ $DRY = 1 ] || mv "$b" "$o"; }
  done
fi
[ $DRY = 1 ] || rm -f "$MANIFEST"
echo "done: removed $removed, kept $kept (project config.yaml/PROJECT_RULES.md are user-owned and left in place)"
