# AGENTS.md — working on this repository
- `skills/` is the single source of truth. Never copy skills into `adapters/`; installers copy from `skills/`.
- Native agent files in `adapters/*/agents/` are GENERATED. Edit `agents/*.md` or `agents/manifest.json`, run `python3 scripts/build-adapters.py`.
- Skill frontmatter: only `name`, `description` (quoted), optional string-valued `metadata`. `name` must equal the directory name. All 11 numbered sections are mandatory (tests enforce).
- Contracts changes follow `contracts/COMPATIBILITY.md` (bump `schema_version` rules + migration log).
- Policies ship in `observe`. Never add a rule that blocks on User-Agent/geo/score alone.
- Never commit secrets. Never widen agent permissions. Read-only agents must stay read-only (`tests/agents`).
- Before finishing: `tests/run_all.sh`. Report results faithfully; static ≠ executed.
- Do not recreate Antigravity workflows (deprecated on 2026-10-19); use skills/rules.
