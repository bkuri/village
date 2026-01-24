# First Task Ever

This example walks through your very first task with Village.

## Prerequisites

- Git repository initialized
- Beads installed (optional but recommended)
- Village installed: `uv pip install -e .`

## Setup

```bash
cd /path/to/your/repo

# Initialize Village runtime
village up

# Check if Village is ready
village ready
```

Expected output from `village ready`:
```
Environment: ✅ Runtime
          ✅ Git repo
Work Available: ✅ Beads ready
```

## Your First Task

Assume Beads reports a ready task: `bd-a3f8`

```bash
# Queue the task (starts it in background)
village queue --n 1
```

Expected output:
```
Starting 1 task(s)...

Tasks started: 1
Tasks failed: 0
```

## Inspect the Worker

```bash
# See active workers
village status --workers
```

Expected output:
```
TASK_ID    STATUS    PANE     AGENT   WINDOW            CLAIMED_AT
bd-a3f8    ACTIVE    %12      worker   worker-1-bd-a3f8  2024-01-23 12:34:56
```

## Resume the Task

```bash
# Attach to the worker pane
village resume bd-a3f8
```

You're now inside a tmux pane with OpenCode running on your task. Work on it as needed.

## Clean Up

When done with the task:

```bash
# Stop the runtime
village down

# Clean up any stale locks
village cleanup --apply
```

## What You Learned

- Village uses `village up` to initialize runtime
- `village queue` starts tasks in background workers
- `village status --workers` shows active work
- `village resume` attaches to workers
- `village down` stops the runtime
- `village cleanup` removes stale locks and orphaned worktrees

## Next Steps

Try these examples:

1. [Custom Agent](../02-configuration/custom-agent.md) - Define your own agent
2. [Queue Multiple](../03-commands/queue-multiple.md) - Queue several tasks at once
3. [Multi-Day Workflow](../05-advanced/workflow.md) - Handle interrupts and cleanup
