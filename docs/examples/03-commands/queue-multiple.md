# Queue Multiple Tasks

This example shows how to queue several tasks across different agent types.

## Use Case

You have multiple ready tasks from Beads:
- `bd-a3f8` - Build task
- `bd-b7c2` - Frontend task
- `bd-d9e3` - Test task
- `bd-e5a4` - Another build task

You want to start 2 workers and execute tasks as they become available.

## Prerequisites

```bash
# Ensure Village is ready
village up
village ready
```

## Queue Multiple Tasks

```bash
# Queue up to 2 tasks from all ready tasks
village queue --n 2
```

Expected output:
```
Starting 2 task(s)...

Tasks started: 2
Tasks failed: 0
```

## Inspect Workers

```bash
# See all active workers
village status --workers
```

Expected output:
```
TASK_ID    STATUS    PANE     AGENT     WINDOW
bd-a3f8    ACTIVE    %12      worker    worker-1-bd-a3f8
bd-b7c2    ACTIVE    %13      worker    worker-2-bd-b7c2
```

## Queue Specific Agent Type

```bash
# Queue only build tasks
village queue --agent build --n 2
```

## Handle Partial Success

If some tasks fail to start:

```bash
# Example output
Tasks started: 1
Tasks failed: 1

Failed tasks:
  - bd-b7c2: Worktree creation failed
```

You can inspect what went wrong and retry:

```bash
# Check for stale locks
village status --orphans

# Clean up
village cleanup --apply

# Retry the failed task
village queue --n 1
```

## Queue with Dry Run

Preview what will be queued without starting:

```bash
# Preview queue plan
village queue --n 3 --dry-run
```

Expected output:
```
QUEUE PLAN
============
Ready: 3 tasks
Available: 3 tasks
Blocked: 0 tasks
Slots available: 3
```

## Next Steps

Try these examples:

1. [Custom Agent](../02-configuration/custom-agent.md) - Define specialized agents
2. [Multiple Agents](../04-configuration/multiple-agents.md) - Use several agent types together
3. [Multi-Day Workflow](../05-advanced/workflow.md) - Handle interrupt recovery
