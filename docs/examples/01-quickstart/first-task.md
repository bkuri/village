# First Task Ever

This example walks through your very first task with Village.

## Prerequisites

- Git repository initialized
- village tasks ready (optional but recommended)
- Village installed: `uv pip install -e .`

## Setup

```bash
cd /path/to/your/repo

# Initialize Village runtime
village up

# Check if Village is ready
village watcher ready
```

Expected output from `village watcher ready`:
```
Environment: ✅ Runtime
          ✅ Git repo
Work Available: ✅ Village tasks ready
```

## Your First Task

Assume village tasks reports a ready task: `village-t1`

```bash
# Queue the task (starts it in background)
village builder queue --n 1
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
village watcher status --system
```

Expected output:
```
TASK_ID    STATUS    PANE     AGENT   WINDOW            CLAIMED_AT
village-t1    ACTIVE    %12      worker   worker-1-village-t1  2024-01-23 12:34:56
```

## Resume the Task

```bash
# Attach to the worker pane
village builder resume --task village-t1
```

You're now inside a tmux pane with OpenCode running on your task. Work on it as needed.

## Clean Up

When done with the task:

```bash
# Stop the runtime
village down

# Clean up any stale locks
village watcher cleanup --apply
```

## What You Learned

- Village uses `village up` to initialize runtime
- `village builder queue` starts tasks in background workers
- `village watcher status --system` shows active work
- `village builder resume` attaches to workers
- `village down` stops the runtime
- `village watcher cleanup` removes stale locks and orphaned worktrees

## Next Steps

Try these examples:

1. [Custom Agent](../02-configuration/custom-agent.md) - Define your own agent
2. [Queue Multiple](../03-commands/queue-multiple.md) - Queue several tasks at once
3. [Multi-Day Workflow](../05-advanced/workflow.md) - Handle interrupts and cleanup
