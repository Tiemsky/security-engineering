# Tool compatibility (official docs consulted 2026-10-16)
| | Claude Code | Antigravity | OpenCode |
|---|---|---|---|
| Skills (SKILL.md) | `~/.claude/skills/<n>/`, `.claude/skills/<n>/` | global `~/.gemini/config/skills/`, workspace `.agents/skills/` (legacy `.agent/skills`) | `~/.config/opencode/skills/`, `.opencode/skills/`; also reads `.claude/skills`, `.agents/skills` |
| Skill frontmatter | all optional; `description` recommended; unknown keys ignored | `description` required, `name` optional (defaults to folder) | `name`+`description` required; name regex `^[a-z0-9]+(-[a-z0-9]+)*$`, ≤64, must equal dir; `metadata` string→string |
| Agents | Markdown+YAML in `.claude/agents/`, `~/.claude/agents/`; `name`,`description` required; `tools`, `disallowedTools`, `model`, `permissionMode`, `skills`… | Markdown+YAML in `.agents/agents/`, `~/.gemini/config/agents/`; `tools[]`, `subagent`, `mainAgent`, `commandExecutionPolicy`, `skills[]` | Markdown in `.opencode/agents/`, `~/.config/opencode/agents/`; filename = name; `description` required, `mode`, `permission` (allow/ask/deny, glob objects) |
| Project instructions | `CLAUDE.md` | `AGENTS.md`/`GEMINI.md`, `.agents/rules/*.md` (frontmatter `trigger` required) | `AGENTS.md`, `opencode.json` `instructions[]` |
| Global rules | `~/.claude/CLAUDE.md` | `~/.gemini/GEMINI.md`, `~/.gemini/config/rules/*.md` | `~/.config/opencode/AGENTS.md` (unverified here) |
| Workflows | n/a | **deprecated: stop working 2026-10-19** → not shipped | n/a |
| Permission model | `tools` allowlist + `permissionMode` | `tools` list + `commandExecutionPolicy` | per-agent `permission` map |

## Decisions that follow
- Skills use the intersection of all three formats (quoted `description`, `name`==dir, string `metadata`).
- OpenCode reads Claude-compatible paths: when both tools are installed the installer **skips OpenCode's own skills copy** to avoid duplicate names.
- Antigravity global skills live in `~/.gemini/config/skills/` (not `~/.agents/skills`, which has a documented crash-loop risk when overloaded). Install a small targeted set only; this project adds exactly 13.

## Known limitations / unverified
- Antigravity subagent tool names beyond `view_file`, `grep_search`, `run_command` (used by working local agents) are **unverified**; the implementer's `write_to_file`/`edit_file` come from skill docs. A misspelled tool name can hang a subagent — keep read-only agents on the verified set (tested). If unsure, run the Implementer role in the main agent.
- Antigravity rules path `~/.gemini/config/rules/` and 24 KB/20k-token limits come from the official rules page; **loading was not exercised** (no Antigravity session was launched).
- OpenCode and Claude Code agent files were checked **statically against documented fields**; no session was launched to prove loading.
- OpenCode global path on native Windows is unverified (installer uses `~/.config/opencode`; override with `-OpenCodeDir`).
- Claude subagents cannot spawn subagents; the orchestrator agent is meant for the main session (`claude --agent` usage unverified) or as a CLAUDE.md-driven procedure.
