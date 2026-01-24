# Village Chat — Slash Commands

## Commands
- `/help [topic]` — show help (topics: commands, tasks, context, files, policy, workflow)
- `/tasks` — list Beads tasks
- `/task <id>` — show task details
- `/ready` — show ready tasks (Beads)
- `/status` — show Village status summary

## Workflow
1. Use chat to clarify intent and write context files.
2. Use Beads to define work.
3. Use `village ready` to validate execution readiness.
4. Use `village queue` / `village resume` to execute.

## Files
By default, chat writes to:
`.village/context/`