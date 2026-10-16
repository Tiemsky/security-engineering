# Installation
Requirements: bash + python3 (Linux/macOS/WSL) or PowerShell 5.1+/7 (Windows). No admin rights. Copy-based (no symlinks: they need privileges/Developer Mode on Windows).

## Global (current user)
```bash
scripts/install.sh --mode global --dry-run          # shows every copy; writes nothing
scripts/install.sh --mode global                    # auto-detects claude / opencode / antigravity (config dir or binary)
scripts/install.sh --mode global --tools claude --claude-dir /custom/.claude
scripts/validate-installation.sh --mode global
scripts/uninstall.sh --mode global [--restore-backups]
```
Targets: Claude `~/.claude/{skills,agents}`; OpenCode `$XDG_CONFIG_HOME|~/.config/opencode/{skills,agents}`; Antigravity `~/.gemini/config/{skills,agents,rules}`; shared `~/.security-engineering/shared/{core,contracts,policies}`; manifest `~/.security-engineering/manifest-global.json`.
WSL: installs into the Linux home; Windows-side configs are never touched unless you pass an explicit `--*-dir`.

## Safety guarantees (tested in `tests/installer`)
- Dry-run writes nothing. Second run = 0 actions (idempotent).
- A destination file that is not ours or was edited since install is a **CONFLICT** (exit 3); `--force` backs it up as `*.bak.<UTC>` first. `uninstall --restore-backups` restores them.
- Unrelated JSON/Markdown is preserved: `opencode.json` is merged key-wise; `CLAUDE.md`/`AGENTS.md` get only a marked `<!-- security-engineering:begin/end -->` block.
- Version checks: downgrade or pin mismatch ⇒ exit 4 unless `--allow-version-change`.
- Permission allowlists, `permissionMode`, shell policies are never modified. No secrets are read or copied.
- Duplicate skill names found under another discovery root are reported as warnings.

## Update / rollback
`git pull` (or checkout a tag) in the central repo → `install.sh --mode global` upgrades files you have not edited. Roll back: checkout the previous tag, re-run with `--allow-version-change`; or `uninstall.sh --restore-backups`.
