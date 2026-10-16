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
# remove now-empty directories upward, but never a tool root (.claude, .opencode, .agents, ...) nor anything above it
prune() { local d="$1"; while [ -d "$d" ] && [ -z "$(ls -A "$d")" ]; do case "$(basename "$d")" in .claude|.opencode|.agents|.gemini|.config|config|opencode|.security-engineering|"$(basename "$HOME")") break;; esac; rmdir "$d"; d="$(dirname "$d")"; done; }
run() { echo "  $([ $DRY = 1 ] && echo '[dry-run] ')$*"; }
removed=0; kept=0
while IFS=$'\t' read -r f h; do
  [ -e "$f" ] || continue
  if [ "$(sha "$f")" = "$h" ]; then run "remove $f"; [ $DRY = 1 ] || { rm -f "$f"; prune "$(dirname "$f")"; }; removed=$((removed+1))
  else echo "  KEEP (modified since install) $f"; kept=$((kept+1)); fi
done < <(python3 -c 'import json,sys;[print(k+"\t"+v) for k,v in json.load(open(sys.argv[1]))["files"].items()]' "$MANIFEST")
CREATED="$(python3 -c 'import json,sys;print("\n".join(json.load(open(sys.argv[1])).get("created",[])))' "$MANIFEST")"
is_created() { printf '%s\n' "$CREATED" | grep -Fxq -- "$1"; }
SCHEMA_ADDED="$(python3 -c 'import json,sys;print("\n".join(json.load(open(sys.argv[1])).get("json_schema_added",[])))' "$MANIFEST")"
while IFS= read -r f; do
  [ -n "$f" ] && [ -f "$f" ] || continue; run "remove managed block from $f"
  [ $DRY = 1 ] || { awk 'BEGIN{s=0} $0=="<!-- security-engineering:begin -->"{s=1;next} $0=="<!-- security-engineering:end -->"{s=0;next} !s{print}' "$f" > "$f.new" && mv "$f.new" "$f"
    if ! grep -q '[^[:space:]]' "$f" && is_created "$f"; then rm -f "$f"; echo "  removed (created by installer, now empty) $f"; fi; }
done < <(python3 -c 'import json,sys;print("\n".join(json.load(open(sys.argv[1])).get("blocks",[])))' "$MANIFEST")
if [ "$MODE" = project ] && [ -f "$PROJECT_DIR/opencode.json" ]; then
  run "remove instructions entry from opencode.json"
  [ $DRY = 1 ] || python3 - "$PROJECT_DIR/opencode.json" "$CREATED" "$SCHEMA_ADDED" <<'PY'
import json,sys,os
p=sys.argv[1]; d=json.load(open(p)); e=".security-engineering/PROJECT_RULES.md"
if e in d.get("instructions",[]): d["instructions"].remove(e)
if not d.get("instructions",True): d.pop("instructions")
created = p in sys.argv[2].split("\n")
if p in sys.argv[3].split("\n"): d.pop("$schema", None)   # we added it; remove it
if created and set(d) <= {"$schema"}: os.remove(p); print("  removed (created by installer, nothing else in it)", p)
else: json.dump(d,open(p,"w"),indent=2); open(p,"a").write("\n")
PY
fi
if [ $RESTORE = 1 ]; then
  while IFS=$'\t' read -r o b; do
    [ -n "$o" ] && [ -f "$b" ] && { run "restore $o from $b"; [ $DRY = 1 ] || mv "$b" "$o"; }
  done < <(python3 -c 'import json,sys;[print(k+"\t"+v) for k,v in json.load(open(sys.argv[1])).get("backups",{}).items()]' "$MANIFEST")
fi
[ $DRY = 1 ] || rm -f "$MANIFEST"
echo "done: removed $removed, kept $kept (project config.yaml/PROJECT_RULES.md are user-owned and left in place)"
