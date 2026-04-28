---
id: guardrails/execution_enforcement
desc: Informs agents of the execution engine, tier system, and enforcement policy.
priority: 100
tags: [safety:enforcement]
---

## Execution Engine Enforcement

All commands are validated by the execution engine before they run. You cannot bypass the engine — all tool calls go through it.

### Tier System

| Tier | Behavior | Examples |
|---|---|---|
| 1 (auto) | Approved without review | read, write, test runs, ls |
| 2 (warn) | Logged, allowed with warning | git add, pip install, rm single file |
| 3 (engine) | Only the execution engine may execute | git commit, git push |
| 4 (blocked) | Rejected outright | rm -rf /, shell pipes, privilege escalation |

### Post-Hoc Verification

Every commit is verified against these policies. Violations block the commit:

- **Content scanning** — no secrets, no placeholders, no debug artifacts
- **TDD compliance** — tests must exist before implementation code
- **Naming conventions** — snake_case enforced for all source files
- **Forbidden patterns** — hardcoded paths, large binaries, forbidden content

### Bypass Prevention

The following protections are active and cannot be circumvented:

- **Plan protocol** — all commands must go through `<plan>` blocks
- **Environment sanitization** — SSH_AUTH_SOCK, PYTHONPATH, LD_PRELOAD stripped at runtime
- **Symlink escape protection** — path traversal attacks are detected and blocked
- **Resource limits** — fork bombs and memory exhaustion are prevented
- **Tamper-proof config** — `.village/` files are read from git history, not the filesystem

### Correct Behavior

1. Propose file writes, reads, and commands via `<plan>` blocks
2. Wait for `<executed>` results from the engine
3. Do NOT attempt to run `git commit`, `git push`, or shell escapes
4. Do NOT try to modify `.village/` config files — they are read-only
5. If a command is blocked, propose an alternative
6. All violations are logged and repeated attempts may terminate the session
