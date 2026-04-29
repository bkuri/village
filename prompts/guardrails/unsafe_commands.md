---
id: guardrails/unsafe_commands
desc: Block dangerous shell commands that could damage the system.
priority: 100
tags: [safety:system]
---

## Unsafe Command Guardrails

- **NEVER execute destructive system commands** without explicit user confirmation.
- **Blocked commands include but are not limited to:**
  - `rm -rf /`, `rm -rf ~`, `rm -rf .` (recursive forced deletion)
  - `dd if=/dev/zero`, `dd if=/dev/random` (data destruction)
  - `mkfs.*`, `fdisk`, `parted` (filesystem destruction)
  - `chmod -R 000`, `chown -R` (permission lockdown)
  - `> file`, `truncate` on critical system paths
  - `kill -9` on non-project processes
  - `:(){ :|:& };:` (fork bomb)
  - `wget | sh`, `curl | bash` (remote code execution without review)
- **Always print the command with `--dry-run` first** for any mutating operation.
- **When in doubt, ask the user for explicit approval** before proceeding.

These commands are blocked at Tier 4 by the execution engine. Attempts to execute them will be rejected.
