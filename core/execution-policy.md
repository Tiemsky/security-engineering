# Execution policy for agents
- Never run destructive commands, production deployments, or tests against production. Use local/CI/ephemeral environments only.
- Never read or print secrets (`.env`, key files). If found in code, report location + type, never the value.
- Never widen permissions (allowlists, `bypassPermissions`, broad `bash`) on your own; ask the user.
- Auditor and Reviewer agents are read-only: no file edits, no network writes, no migrations.
- Implementer changes only files inside the approved plan; one concern per change; tests ship with the change.
- Do not overwrite existing user config without backup and explicit approval.
- Report outcomes faithfully: failures with output, skipped steps as skipped.
