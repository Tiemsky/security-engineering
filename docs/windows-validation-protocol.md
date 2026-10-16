# Native Windows validation protocol for `install.ps1` / `uninstall.ps1` — status: NOT EXECUTED
No Windows host was available. Everything below must be run on Windows 10/11 with **Windows PowerShell 5.1** and again with **PowerShell 7**, as a standard (non-admin) user, in a throw-away profile or VM. Record OS build, `$PSVersionTable`, and paste outputs in `docs/validation-v0.1.0.md`.
What is already covered (PowerShell 7.4 **on Linux**, Docker): dry-run, idempotency, JSON/Markdown preservation, pre-existing identical file adoption, uninstall of managed files only, paths with spaces. NOT covered by that run and therefore to verify on Windows:
1. Paths: `$env:USERPROFILE` vs `$HOME`, `\` separators in manifests, long paths (>260), spaces/non-ASCII in the user name, OneDrive-redirected profile.
2. Encoding/line endings: files written as UTF-8 without BOM; `CLAUDE.md`/`AGENTS.md` with CRLF are updated without corrupting the managed block; `opencode.json` stays valid JSON for OpenCode.
3. File behaviour: read-only attribute, files locked by a running tool (Claude/OpenCode/Antigravity open), antivirus quarantine; installer must report, not crash, and leave the manifest consistent.
4. ACLs: install into a directory where the user lacks write permission → clear error, no partial manifest.
5. Default OpenCode global path on native Windows (installer assumes `~/.config/opencode`; confirm with `opencode debug paths` and pass `-OpenCodeDir` if different) and Antigravity/Claude global paths.
6. `Get-FileHash` hash equality with Linux-generated manifests is irrelevant (manifests are per-machine); confirm `install.ps1 -Mode global` ×2 → "0 action(s)".
7. Execution policy: `powershell -ExecutionPolicy Bypass -File scripts\install.ps1 ...` works without admin; document if scripts must be unblocked (`Unblock-File`).
Pass criteria: install → validate (manually compare hashes or run `validate-installation.sh` under WSL against the same files) → upgrade → conflict → uninstall all behave as in `tests/installer/*` and nothing outside the managed files changes (diff the profile before/after).
