# Queue Multiple Tasks

This example shows how to queue several tasks across different agent types.

## Use Case

You have multiple ready tasks from village tasks:
- `village-t1` - Build task
- `village-t2` - Frontend task
- `village-t3` - Test task
- `village-t4` - Another build task

You want to start 2 workers and execute tasks as they become available.

## Prerequisites

```bash
# Ensure Village is ready
village up
village watcher ready
```

## Queue Multiple Tasks

```bash
# Queue up to 2 tasks from all ready tasks
village builder queue --n 2
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
village watcher status --system
```

Expected output:
```
TASK_ID      STATUS    PANE     AGENT     WINDOW
village-t1    ACTIVE    %12      worker    worker-1-village-t1
village-t2    ACTIVE    %13      worker    worker-2-village-t2
```

## Queue Specific Agent Type

```bash
# Queue only build tasks
village builder queue --agent build --n 2
```

## Handle Partial Success

If some tasks fail to start:

```bash
# Example output
Tasks started: 1
Tasks failed: 1

Failed tasks:
  - village-t2: Worktree creation failed
```

You can inspect what went wrong and retry:

```bash
# Check for stale locks
village watcher status --system

# Clean up
village watcher cleanup --apply

# Retry the failed task
village builder queue --n 1
```

## Queue with Dry Run

Preview what will be queued without starting:

```bash
# Preview queue plan
village builder queue --n 3 --dry-run
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
