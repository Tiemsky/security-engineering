#!/usr/bin/env bash
# security-engineering installer (Linux, macOS, WSL). Copy-based, idempotent, manifest-tracked, dry-run capable.
# Usage: install.sh --mode global|project [--tools claude,opencode,antigravity] [--project-dir DIR] [--dry-run] [--force]
#        [--vendor-skills] [--allow-version-change] [--claude-dir D] [--opencode-dir D] [--antigravity-dir D] [--shared-dir D] [--framework F]
# Exit codes: 0 ok · 2 usage · 3 conflicts left unresolved (re-run with --force after review) · 4 version refusal
set -euo pipefail
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VERSION="$(tr -d '[:space:]' < "$SRC/VERSION")"
MODE=""; TOOLS=""; PROJECT_DIR=""; DRY=0; FORCE=0; VENDOR=0; ALLOW_VER=0; FRAMEWORK=""
CLAUDE_DIR=""; OPENCODE_DIR=""; ANTIGRAVITY_DIR=""; SHARED_DIR=""
TS="$(date -u +%Y%m%dT%H%M%SZ)"; CONFLICTS=0; ACTIONS=0

usage() { sed -n '2,6p' "$0"; exit 2; }
while [ $# -gt 0 ]; do case "$1" in
  --mode) MODE="$2"; shift 2;; --tools) TOOLS="$2"; shift 2;; --project-dir) PROJECT_DIR="$2"; shift 2;;
  --dry-run) DRY=1; shift;; --force) FORCE=1; shift;; --vendor-skills) VENDOR=1; shift;; --allow-version-change) ALLOW_VER=1; shift;;
  --claude-dir) CLAUDE_DIR="$2"; shift 2;; --opencode-dir) OPENCODE_DIR="$2"; shift 2;; --antigravity-dir) ANTIGRAVITY_DIR="$2"; shift 2;;
  --shared-dir) SHARED_DIR="$2"; shift 2;; --framework) FRAMEWORK="$2"; shift 2;; -h|--help) usage;; *) echo "unknown option: $1" >&2; usage;;
esac; done
[ "$MODE" = global ] || [ "$MODE" = project ] || usage

# ---- environment detection ------------------------------------------------------------------
OS="$(uname -s)"; WSL=0; grep -qi microsoft /proc/version 2>/dev/null && WSL=1
HOME_DIR="${HOME:?HOME not set}"
say() { printf '%s\n' "$*"; }
say "security-engineering $VERSION · os=$OS wsl=$WSL mode=$MODE dry_run=$DRY"
[ "$WSL" = 1 ] && say "note: WSL detected — installing into the Linux home. Windows-side tool configs (/mnt/c/Users/...) are NOT touched; pass --claude-dir/--opencode-dir/--antigravity-dir to target them explicitly."

if [ "$MODE" = global ]; then
  : "${CLAUDE_DIR:=$HOME_DIR/.claude}"; : "${OPENCODE_DIR:=${XDG_CONFIG_HOME:-$HOME_DIR/.config}/opencode}"; : "${ANTIGRAVITY_DIR:=$HOME_DIR/.gemini/config}"
  : "${SHARED_DIR:=$HOME_DIR/.security-engineering/shared}"; ROOT_STATE="$HOME_DIR/.security-engineering"
  SK_CLAUDE="$CLAUDE_DIR/skills"; AG_CLAUDE="$CLAUDE_DIR/agents"; SK_OPEN="$OPENCODE_DIR/skills"; AG_OPEN="$OPENCODE_DIR/agents"
  SK_ANTI="$ANTIGRAVITY_DIR/skills"; AG_ANTI="$ANTIGRAVITY_DIR/agents"; RULES_ANTI="$ANTIGRAVITY_DIR/rules"
  DETECT_CLAUDE="$CLAUDE_DIR"; DETECT_OPEN="$OPENCODE_DIR"; DETECT_ANTI="$ANTIGRAVITY_DIR"; INSTALL_SKILLS=1
else
  PROJECT_DIR="$(cd "${PROJECT_DIR:?--project-dir required in project mode}" && pwd)"
  : "${CLAUDE_DIR:=$PROJECT_DIR/.claude}"; : "${OPENCODE_DIR:=$PROJECT_DIR/.opencode}"; : "${ANTIGRAVITY_DIR:=$PROJECT_DIR/.agents}"
  ROOT_STATE="$PROJECT_DIR/.security-engineering"; : "${SHARED_DIR:=$ROOT_STATE/shared}"
  SK_CLAUDE="$CLAUDE_DIR/skills"; AG_CLAUDE="$CLAUDE_DIR/agents"; SK_OPEN="$OPENCODE_DIR/skills"; AG_OPEN="$OPENCODE_DIR/agents"
  SK_ANTI="$ANTIGRAVITY_DIR/skills"; AG_ANTI="$ANTIGRAVITY_DIR/agents"; RULES_ANTI="$ANTIGRAVITY_DIR/rules"
  INSTALL_SKILLS=$VENDOR
  DETECT_CLAUDE=""; DETECT_OPEN=""; DETECT_ANTI=""
fi
MANIFEST="$ROOT_STATE/manifest-$MODE.json"

if [ -z "$TOOLS" ]; then   # auto-detect from existing config dirs / binaries
  if [ "$MODE" = global ]; then
    { [ -d "$DETECT_CLAUDE" ] || command -v claude >/dev/null 2>&1; } && TOOLS="claude"
    { [ -d "$DETECT_OPEN" ] || command -v opencode >/dev/null 2>&1; } && TOOLS="${TOOLS:+$TOOLS,}opencode"
    { [ -d "$DETECT_ANTI" ] || command -v agy >/dev/null 2>&1; } && TOOLS="${TOOLS:+$TOOLS,}antigravity"
  else TOOLS="claude,opencode,antigravity"; fi
fi
[ -n "$TOOLS" ] || { say "no supported tool detected; pass --tools"; exit 2; }
has() { case ",$TOOLS," in *",$1,"*) return 0;; esac; return 1; }
say "tools: $TOOLS"

# ---- primitives -----------------------------------------------------------------------------
sha() { if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi; }
NEWMAN="$(mktemp)"; trap 'rm -f "$NEWMAN" "$NEWMAN.bak"' EXIT
old_sha() {
  [ -f "$MANIFEST" ] || return 0
  python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("files",{}).get(sys.argv[2],""))' "$MANIFEST" "$1"
}
record() { printf '%s\t%s\n' "$1" "$2" >> "$NEWMAN"; }   # path<TAB>sha

# install_file SRC DST : copy honoring idempotency, ownership (manifest) and conflicts
install_file() {
  local s="$1" d="$2" ss; ss="$(sha "$s")"
  if [ ! -e "$d" ]; then act "copy  $d"; [ $DRY = 1 ] || { mkdir -p "$(dirname "$d")"; cp "$s" "$d"; }; record "$d" "$ss"; return; fi
  local ds os; ds="$(sha "$d")"; os="$(old_sha "$d")"
  if [ "$ds" = "$ss" ]; then   # already current (idempotent). Record ownership ONLY if a previous install created it; a pre-existing identical file stays the user's.
    if [ -n "$os" ]; then record "$d" "$ss"; else say "  adopted (pre-existing, identical, left unmanaged): $d"; fi; return; fi
  if [ -n "$os" ] && [ "$os" = "$ds" ]; then act "update $d"; [ $DRY = 1 ] || cp "$s" "$d"; record "$d" "$ss"; return; fi   # ours, unmodified → upgrade
  if [ $FORCE = 1 ]; then act "backup+overwrite $d (-> $d.bak.$TS)"; [ $DRY = 1 ] || { cp "$d" "$d.bak.$TS"; cp "$s" "$d"; }; record "$d" "$ss"; BACKUPS+=("$d"$'\t'"$d.bak.$TS"); return; fi
  say "CONFLICT $d exists and is not managed/unmodified by this installer (use --force to back up and overwrite)"; CONFLICTS=$((CONFLICTS+1))
}
act() { ACTIONS=$((ACTIONS+1)); say "  $([ $DRY = 1 ] && echo '[dry-run] ')$*"; }
BACKUPS=()

install_tree() {  # install_tree SRC_DIR DST_DIR
  local f rel; while IFS= read -r -d '' f; do rel="${f#"$1"/}"; install_file "$f" "$2/$rel"; done < <(find "$1" -type f ! -name '.DS_Store' -print0 | sort -z)
}
warn_duplicates() {  # skill present under another discovery root with the same name
  local sk="$1" target_root="$2" r; for r in "$HOME_DIR/.claude/skills" "$HOME_DIR/.agents/skills" "${XDG_CONFIG_HOME:-$HOME_DIR/.config}/opencode/skills" "$HOME_DIR/.gemini/config/skills"; do
    [ "$r" != "$target_root" ] && [ -d "$r/$sk" ] && say "WARNING duplicate skill name '$sk' also at $r/$sk (tools may load both)"
  done; return 0
}
install_skills() {  # install_skills TARGET_ROOT
  local sk; for d in "$SRC"/skills/*/; do d="${d%/}"; sk="$(basename "$d")"; [ "$MODE" = global ] && warn_duplicates "$sk" "$1"; install_tree "$d" "$1/$sk"; done
}

# ---- version guards -------------------------------------------------------------------------
if [ -f "$MANIFEST" ]; then
  prev="$(python3 -c 'import json,sys;print(json.load(open(sys.argv[1])).get("version",""))' "$MANIFEST")"
  if [ -n "$prev" ] && [ "$prev" != "$VERSION" ]; then
    newest="$(printf '%s\n%s\n' "$prev" "$VERSION" | sort -V | tail -1)"
    if [ "$newest" = "$prev" ] && [ $ALLOW_VER = 0 ]; then say "REFUSED: installed $prev is newer than source $VERSION (downgrade). Use --allow-version-change."; exit 4; fi
    say "upgrading $prev -> $VERSION"
  fi
fi
PCFG="$ROOT_STATE/config.yaml"
if [ "$MODE" = project ] && [ -f "$PCFG" ]; then
  pin="$(sed -n 's/^security_engineering_version:[[:space:]]*"\{0,1\}\([0-9][0-9.]*\)"\{0,1\}.*/\1/p' "$PCFG" | head -1)"
  if [ -n "$pin" ] && [ "$pin" != "$VERSION" ] && [ $ALLOW_VER = 0 ]; then say "REFUSED: project pins $pin but source is $VERSION. Review, then re-run with --allow-version-change to move the pin."; exit 4; fi
fi

# ---- shared resources -----------------------------------------------------------------------
say "shared resources -> $SHARED_DIR"
for d in core contracts policies; do install_tree "$SRC/$d" "$SHARED_DIR/$d"; done

# ---- per tool -------------------------------------------------------------------------------
if has claude; then
  say "claude-code"; [ $INSTALL_SKILLS = 1 ] && install_skills "$SK_CLAUDE"; install_tree "$SRC/adapters/claude-code/agents" "$AG_CLAUDE"
fi
if has opencode; then
  say "opencode"
  if [ $INSTALL_SKILLS = 1 ]; then
    if has claude && [ "$SK_CLAUDE" != "$SK_OPEN" ]; then say "  skills: skipped (OpenCode also discovers Claude-compatible skill paths; avoids duplicates)"; else install_skills "$SK_OPEN"; fi
  fi
  install_tree "$SRC/adapters/opencode/agents" "$AG_OPEN"
fi
if has antigravity; then
  say "antigravity"; [ $INSTALL_SKILLS = 1 ] && install_skills "$SK_ANTI"
  install_tree "$SRC/adapters/antigravity/agents" "$AG_ANTI"; install_tree "$SRC/adapters/antigravity/rules" "$RULES_ANTI"
fi

# ---- project integration package ------------------------------------------------------------
sub() { sed -e "s/{{VERSION}}/$VERSION/g" -e "s/{{FRAMEWORK}}/${FRAMEWORK:-generic}/g" "$1"; }
managed_block() {  # managed_block FILE TEMPLATE : insert/replace our marked block, preserve all other content
  local f="$1" t="$2" begin="<!-- security-engineering:begin -->" end="<!-- security-engineering:end -->" tmp; tmp="$(mktemp)"
  { echo "$begin"; sub "$t"; echo "$end"; } > "$tmp"
  if [ -f "$f" ] && grep -qF "$begin" "$f"; then
    local new; new="$(mktemp)"; awk -v b="$begin" -v e="$end" -v blk="$tmp" 'BEGIN{skip=0} $0==b{while((getline l<blk)>0)print l; skip=1; next} $0==e{skip=0; next} !skip{print}' "$f" > "$new"
    if cmp -s "$new" "$f"; then rm -f "$new" "$tmp"; return; fi
    act "update managed block in $f"; [ $DRY = 1 ] || { cp "$f" "$f.bak.$TS"; cp "$new" "$f"; }; rm -f "$new"
  else
    act "append managed block to $f"; [ -f "$f" ] || CREATED+=("$f"); [ $DRY = 1 ] || { [ -f "$f" ] && cp "$f" "$f.bak.$TS"; { [ -f "$f" ] && cat "$f" && echo; cat "$tmp"; } > "$f.new"; mv "$f.new" "$f"; }
  fi
  rm -f "$tmp"; BLOCKS+=("$f")
}
BLOCKS=(); CREATED=(); SCHEMA_ADDED=""
if [ "$MODE" = project ]; then
  if [ -z "$FRAMEWORK" ]; then
    if grep -q '"laravel/framework"' "$PROJECT_DIR/composer.json" 2>/dev/null; then FRAMEWORK=laravel
    elif grep -q '"@nestjs/core"' "$PROJECT_DIR/package.json" 2>/dev/null; then FRAMEWORK=nestjs; else FRAMEWORK=generic; fi
  fi
  say "project integration (framework=$FRAMEWORK)"
  if [ ! -f "$PCFG" ]; then act "create $PCFG"; [ $DRY = 1 ] || { mkdir -p "$ROOT_STATE"; sub "$SRC/adapters/project/config.yaml.template" > "$PCFG"; }
  elif [ $ALLOW_VER = 1 ]; then act "move pin in $PCFG to $VERSION"; [ $DRY = 1 ] || { cp "$PCFG" "$PCFG.bak.$TS"; sed -i.tmp "s/^security_engineering_version:.*/security_engineering_version: \"$VERSION\"/" "$PCFG"; rm -f "$PCFG.tmp"; }; fi
  [ -f "$ROOT_STATE/PROJECT_RULES.md" ] || { act "create $ROOT_STATE/PROJECT_RULES.md"; [ $DRY = 1 ] || { mkdir -p "$ROOT_STATE"; sub "$SRC/adapters/project/PROJECT_RULES.md.template" > "$ROOT_STATE/PROJECT_RULES.md"; }; }
  has claude && managed_block "$PROJECT_DIR/CLAUDE.md" "$SRC/adapters/claude-code/CLAUDE.md.template"
  { has opencode || has antigravity; } && managed_block "$PROJECT_DIR/AGENTS.md" "$SRC/adapters/opencode/AGENTS.md.template"
  if has opencode; then   # merge, never replace, opencode.json
    OC="$PROJECT_DIR/opencode.json"
    if [ ! -f "$OC" ]; then act "create $OC"; CREATED+=("$OC"); [ $DRY = 1 ] || cp "$SRC/adapters/opencode/opencode.json.template" "$OC"
    elif python3 -c 'import json,sys;d=json.load(open(sys.argv[1]));sys.exit(0 if ".security-engineering/PROJECT_RULES.md" in d.get("instructions",[]) and "$schema" in d else 1)' "$OC"; then :   # already merged
    else act "merge instructions entry into $OC (other keys preserved; backup kept)"; grep -q '"\$schema"' "$OC" || SCHEMA_ADDED="$OC"; [ $DRY = 1 ] || { cp "$OC" "$OC.bak.$TS"; python3 - "$OC" <<'PY'
import json,sys
p=sys.argv[1]; d=json.load(open(p)); e=".security-engineering/PROJECT_RULES.md"
ins=d.setdefault("instructions",[]); 
if e not in ins: ins.append(e)
d.setdefault("$schema","https://opencode.ai/config.json")
json.dump(d,open(p,"w"),indent=2); open(p,"a").write("\n")
PY
    }; fi
  fi
fi

# ---- manifest -------------------------------------------------------------------------------
if [ $DRY = 0 ]; then
  mkdir -p "$ROOT_STATE"
  nl() { [ $# -eq 0 ] || printf '%s\n' "$@"; }
  python3 - "$MANIFEST" "$VERSION" "$NEWMAN" "$TS" "$(nl "${BLOCKS[@]+"${BLOCKS[@]}"}")" "$(nl "${BACKUPS[@]+"${BACKUPS[@]}"}")" "$MODE" "$(nl "${CREATED[@]+"${CREATED[@]}"}")" "$SCHEMA_ADDED" <<'PY'
import json,sys,os
mp,ver,newf,ts,blocks,backups,mode,created,schema_added=sys.argv[1:10]
L=lambda x:[i for i in x.split("\n") if i]
old=json.load(open(mp)) if os.path.exists(mp) else {}
files=dict(l.rstrip("\n").split("\t") for l in open(newf) if "\t" in l)
bk=old.get("backups",{}); bk.update(dict(b.split("\t",1) for b in L(backups) if "\t" in b))
new={"version":ver,"mode":mode,"installed_at":ts,"files":{**old.get("files",{}),**files},"blocks":sorted(set(old.get("blocks",[])+L(blocks))),"backups":bk,"created":sorted(set(old.get("created",[])+L(created))),"json_schema_added":old.get("json_schema_added",[])}
if schema_added: new["json_schema_added"]=sorted(set(new["json_schema_added"]+[schema_added]))
if old and {k:v for k,v in old.items() if k!="installed_at"}=={k:v for k,v in new.items() if k!="installed_at"}: sys.exit(0)   # unchanged -> idempotent
json.dump(new,open(mp,"w"),indent=2)
PY
  say "manifest: $MANIFEST"
fi
say "done: $ACTIONS action(s), $CONFLICTS conflict(s)$([ $DRY = 1 ] && echo ' (dry-run: nothing written)')"
[ $CONFLICTS -eq 0 ] || exit 3
