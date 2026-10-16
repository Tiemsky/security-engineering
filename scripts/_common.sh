# shared by uninstall/validate: resolve state paths exactly like install.sh
resolve_paths() {
  HOME_DIR="${HOME:?}"
  if [ "$MODE" = global ]; then ROOT_STATE="$HOME_DIR/.security-engineering"; else PROJECT_DIR="$(cd "${PROJECT_DIR:?--project-dir required}" && pwd)"; ROOT_STATE="$PROJECT_DIR/.security-engineering"; fi
  MANIFEST="$ROOT_STATE/manifest-$MODE.json"
}
sha() { if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | cut -d' ' -f1; else shasum -a 256 "$1" | cut -d' ' -f1; fi; }
